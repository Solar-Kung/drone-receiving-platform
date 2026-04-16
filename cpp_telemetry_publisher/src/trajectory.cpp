#include "telemetry_publisher/trajectory.h"

#include <cassert>
#include <cmath>
#include <numbers>

namespace tp {

namespace {
constexpr double kEarthRadiusM = 6'371'000.0;
constexpr double kPi           = std::numbers::pi;

double deg2rad(double d) { return d * kPi / 180.0; }
double rad2deg(double r) { return r * 180.0 / kPi; }
}  // namespace

// ── Trajectory ────────────────────────────────────────────────────────────────

Trajectory::Trajectory(TrajectoryConfig config) : config_(std::move(config)) {}

bool Trajectory::empty() const { return config_.waypoints.empty(); }

void Trajectory::reset() {
    current_segment_  = 0;
    segment_progress_ = 0.0;
    hold_elapsed_sec_ = 0.0;
    holding_          = false;
}

std::optional<Position> Trajectory::advance(std::chrono::milliseconds delta) {
    const auto& wps = config_.waypoints;
    if (wps.empty()) return std::nullopt;

    // A single waypoint: just hover forever.
    if (wps.size() == 1) {
        return Position{wps[0].lat, wps[0].lon, wps[0].alt, 0.0, 0.0};
    }

    double dt_sec = delta.count() / 1000.0;

    // ── Holding at a waypoint ──────────────────────────────────────────────
    if (holding_) {
        hold_elapsed_sec_ += dt_sec;
        const Waypoint& wp = wps[current_segment_];
        if (hold_elapsed_sec_ >= wp.hold_sec) {
            hold_elapsed_sec_ = 0.0;
            holding_          = false;
            // Move to next segment
            ++current_segment_;
            if (current_segment_ >= wps.size() - 1) {
                if (config_.loop) {
                    reset();
                } else {
                    return std::nullopt;  // Route finished
                }
            }
        }
        // While holding, return position of current waypoint
        return Position{wp.lat, wp.lon, wp.alt, 0.0, 0.0};
    }

    // ── Traversing a segment ───────────────────────────────────────────────
    if (current_segment_ >= wps.size() - 1) {
        if (config_.loop) {
            reset();
        } else {
            return std::nullopt;
        }
    }

    const Waypoint& from = wps[current_segment_];
    const Waypoint& to   = wps[current_segment_ + 1];

    double segment_dist_m = haversine_m(from.lat, from.lon, to.lat, to.lon);
    double heading        = bearing_deg(from.lat, from.lon, to.lat, to.lon);
    double alt_delta      = to.alt - from.alt;

    if (segment_dist_m < 1e-6) {
        // Degenerate zero-length segment: skip straight to next waypoint
        ++current_segment_;
        segment_progress_ = 0.0;
        return advance(delta);  // Recurse with same delta
    }

    double travel_m = config_.speed_mps * dt_sec;
    double frac     = travel_m / segment_dist_m;
    segment_progress_ += frac;

    if (segment_progress_ >= 1.0) {
        // Arrived at the next waypoint
        segment_progress_ = 0.0;
        Position pos{to.lat, to.lon, to.alt, config_.speed_mps, heading};

        if (to.hold_sec > 0.0) {
            holding_ = true;
        } else {
            ++current_segment_;
            if (current_segment_ >= wps.size() - 1) {
                if (config_.loop) {
                    reset();
                }
                // else: will return nullopt on next call
            }
        }
        return pos;
    }

    // Interpolate lat/lon/alt linearly along the segment
    double t   = segment_progress_;
    double lat = from.lat + t * (to.lat - from.lat);
    double lon = from.lon + t * (to.lon - from.lon);
    double alt = from.alt + t * alt_delta;

    return Position{lat, lon, alt, config_.speed_mps, heading};
}

// ── Static helpers ─────────────────────────────────────────────────────────────

double Trajectory::haversine_m(double lat1, double lon1, double lat2, double lon2) {
    double dlat = deg2rad(lat2 - lat1);
    double dlon = deg2rad(lon2 - lon1);
    double a    = std::sin(dlat / 2) * std::sin(dlat / 2) +
               std::cos(deg2rad(lat1)) * std::cos(deg2rad(lat2)) *
                   std::sin(dlon / 2) * std::sin(dlon / 2);
    return kEarthRadiusM * 2.0 * std::atan2(std::sqrt(a), std::sqrt(1.0 - a));
}

double Trajectory::bearing_deg(double lat1, double lon1, double lat2, double lon2) {
    double y = std::sin(deg2rad(lon2 - lon1)) * std::cos(deg2rad(lat2));
    double x = std::cos(deg2rad(lat1)) * std::sin(deg2rad(lat2)) -
               std::sin(deg2rad(lat1)) * std::cos(deg2rad(lat2)) *
                   std::cos(deg2rad(lon2 - lon1));
    return std::fmod(rad2deg(std::atan2(y, x)) + 360.0, 360.0);
}

}  // namespace tp
