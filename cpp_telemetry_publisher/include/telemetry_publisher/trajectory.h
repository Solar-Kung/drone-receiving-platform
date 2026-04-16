#pragma once

#include "telemetry_publisher/config.h"

#include <chrono>
#include <optional>

namespace tp {

/// Current position produced by the trajectory engine.
struct Position {
    double lat{};
    double lon{};
    double alt{};
    double speed_mps{};
    double heading_deg{};
};

/// Computes drone positions via linear interpolation between waypoints.
///
/// The trajectory walks through each segment at a constant speed defined by
/// TrajectoryConfig::speed_mps.  At each waypoint the drone hovers for
/// hold_sec before moving to the next one.  When the last waypoint is reached
/// and loop=true the trajectory resets to the beginning automatically.
class Trajectory {
public:
    explicit Trajectory(TrajectoryConfig config);

    /// Advance the simulation by `delta` and return the current position.
    /// Returns nullopt when the route is finished and loop is disabled.
    std::optional<Position> advance(std::chrono::milliseconds delta);

    /// Reset to the first waypoint.
    void reset();

    /// True when the route has no waypoints.
    bool empty() const;

private:
    /// Haversine distance between two lat/lon points (metres).
    static double haversine_m(double lat1, double lon1, double lat2, double lon2);
    /// Bearing from point 1 → point 2 (degrees, 0 = North, clockwise).
    static double bearing_deg(double lat1, double lon1, double lat2, double lon2);

    TrajectoryConfig config_;
    size_t current_segment_{0};
    double segment_progress_{0.0};  ///< Fraction of current segment, 0–1.
    double hold_elapsed_sec_{0.0};  ///< Time spent hovering at current waypoint.
    bool   holding_{false};         ///< True when hovering at a waypoint.
};

}  // namespace tp
