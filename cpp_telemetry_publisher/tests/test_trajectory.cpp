#include "telemetry_publisher/trajectory.h"

#include <gtest/gtest.h>

using namespace tp;
using ms = std::chrono::milliseconds;

// Helper: make a two-waypoint config at a given speed
static TrajectoryConfig two_point_cfg(double speed_mps = 10.0) {
    return TrajectoryConfig{
        .waypoints = {
            {25.0330, 121.5654, 0.0,   0.0},
            {25.0360, 121.5690, 100.0, 0.0},
        },
        .speed_mps = speed_mps,
    };
}

// ── empty / edge cases ─────────────────────────────────────────────────────────

TEST(Trajectory, EmptyWaypointsReturnsNullopt) {
    Trajectory t(TrajectoryConfig{});
    EXPECT_TRUE(t.empty());
    EXPECT_FALSE(t.advance(ms{100}).has_value());
}

TEST(Trajectory, SingleWaypointAlwaysReturnsIt) {
    TrajectoryConfig cfg{.waypoints = {{25.0, 121.0, 50.0, 0.0}}, .speed_mps = 10.0};
    Trajectory t(std::move(cfg));
    ASSERT_FALSE(t.empty());
    auto pos = t.advance(ms{100});
    ASSERT_TRUE(pos.has_value());
    EXPECT_DOUBLE_EQ(pos->lat, 25.0);
    EXPECT_DOUBLE_EQ(pos->lon, 121.0);
    EXPECT_DOUBLE_EQ(pos->alt, 50.0);
}

// ── interpolation ──────────────────────────────────────────────────────────────

TEST(Trajectory, MidpointIsInterpolated) {
    // Two waypoints ~333 m apart (approx). Speed 10 m/s → ~33 s to traverse.
    // After 1 tick of 100 ms the drone should be slightly past the start.
    Trajectory t(two_point_cfg(10.0));

    auto pos0 = t.advance(ms{100});
    ASSERT_TRUE(pos0.has_value());
    // Should still be very close to start
    EXPECT_GT(pos0->lat, 25.0330);
    EXPECT_LT(pos0->lat, 25.0360);
}

TEST(Trajectory, AltitudeInterpolatedBetweenWaypoints) {
    Trajectory t(two_point_cfg(10.0));
    // Advance until we're past the mid-point in altitude (~50 s)
    std::optional<Position> pos;
    for (int i = 0; i < 250; ++i) {
        pos = t.advance(ms{200});
        if (!pos) break;
        if (pos->alt > 50.0) break;
    }
    ASSERT_TRUE(pos.has_value());
    EXPECT_GT(pos->alt, 0.0);
    EXPECT_LE(pos->alt, 100.0);
}

// ── loop mode ──────────────────────────────────────────────────────────────────

TEST(Trajectory, LoopRestartAfterCompletion) {
    TrajectoryConfig cfg{
        .waypoints = {
            {25.0330, 121.5654, 0.0, 0.0},
            {25.0331, 121.5655, 0.0, 0.0},
        },
        .speed_mps = 1000.0,  // Very fast: traverse in < 1 ms
    };
    cfg.loop = true;
    Trajectory t(std::move(cfg));

    // Advance far into the future — should never return nullopt
    for (int i = 0; i < 100; ++i) {
        auto pos = t.advance(ms{1000});
        EXPECT_TRUE(pos.has_value()) << "Loop should restart, iteration " << i;
    }
}

TEST(Trajectory, NoLoopReturnsNulloptAtEnd) {
    TrajectoryConfig cfg{
        .waypoints = {
            {25.0330, 121.5654, 0.0, 0.0},
            {25.0331, 121.5655, 0.0, 0.0},
        },
        .speed_mps = 1000.0,
    };
    cfg.loop = false;
    Trajectory t(std::move(cfg));

    std::optional<Position> pos;
    for (int i = 0; i < 200; ++i) {
        pos = t.advance(ms{1000});
        if (!pos) break;
    }
    EXPECT_FALSE(pos.has_value());
}

// ── hold / hover ───────────────────────────────────────────────────────────────

TEST(Trajectory, HoldSecPausesAtWaypoint) {
    TrajectoryConfig cfg{
        .waypoints = {
            {25.0330, 121.5654, 0.0,  0.0},
            {25.0331, 121.5655, 0.0,  5.0},  // hold 5 s here
            {25.0332, 121.5656, 0.0,  0.0},
        },
        .speed_mps = 1000.0,  // Get there instantly
    };
    Trajectory t(std::move(cfg));

    // Should arrive at WP1 quickly then stay there
    Position last{};
    for (int i = 0; i < 10; ++i) {
        auto pos = t.advance(ms{100});
        ASSERT_TRUE(pos.has_value());
        if (pos->lat >= 25.0331 - 1e-9) {
            last = *pos;
            break;
        }
    }
    // A few more ticks should still be at WP1
    for (int i = 0; i < 10; ++i) {
        auto pos = t.advance(ms{200});
        ASSERT_TRUE(pos.has_value());
        // Should remain near WP1 during hold
        EXPECT_NEAR(pos->lat, 25.0331, 1e-6);
    }
}
