#include "telemetry_publisher/telemetry_generator.h"
#include "telemetry_publisher/config.h"
#include "telemetry_publisher/trajectory.h"
#include "telemetry.pb.h"

#include <gtest/gtest.h>
#include <chrono>

using namespace tp;
using ms = std::chrono::milliseconds;

namespace {

SimulationConfig default_sim() {
    return SimulationConfig{
        .battery_drain_per_second = 0.1,
        .signal_base              = 90.0,
        .signal_noise             = 2.0,
        .loop                     = true,
    };
}

Position default_pos() {
    return Position{25.033, 121.565, 100.0, 10.0, 45.0};
}

}  // namespace

// ── Sequence number ────────────────────────────────────────────────────────────

TEST(TelemetryGenerator, SequenceIncrementsMonotonically) {
    TelemetryGenerator gen("test-drone", default_sim());
    auto pos = default_pos();

    auto pkt0 = gen.generate(pos, ms{0});
    auto pkt1 = gen.generate(pos, ms{100});
    auto pkt2 = gen.generate(pos, ms{200});

    EXPECT_EQ(pkt0.sequence(), 0u);
    EXPECT_EQ(pkt1.sequence(), 1u);
    EXPECT_EQ(pkt2.sequence(), 2u);
}

// ── Battery drain ──────────────────────────────────────────────────────────────

TEST(TelemetryGenerator, BatteryDrainsWithElapsedTime) {
    TelemetryGenerator gen("test-drone", default_sim());
    auto pos = default_pos();

    // At t=0 battery should be ~100 %
    auto pkt0 = gen.generate(pos, ms{0});
    EXPECT_NEAR(pkt0.battery_percent(), 100.0, 0.01);

    // At t=10 s, drain = 0.1 * 10 = 1 %
    auto pkt1 = gen.generate(pos, ms{10'000});
    EXPECT_NEAR(pkt1.battery_percent(), 99.0, 0.01);

    // At t=100 s, drain = 0.1 * 100 = 10 %
    auto pkt2 = gen.generate(pos, ms{100'000});
    EXPECT_NEAR(pkt2.battery_percent(), 90.0, 0.01);
}

TEST(TelemetryGenerator, BatteryNeverGoesNegative) {
    TelemetryGenerator gen("test-drone", default_sim());
    auto pos = default_pos();

    // Far future: battery should clamp to 0
    auto pkt = gen.generate(pos, ms{10'000'000});  // ~167 min
    EXPECT_GE(pkt.battery_percent(), 0.0);
}

// ── Timestamp ──────────────────────────────────────────────────────────────────

TEST(TelemetryGenerator, TimestampIsCurrentEpochMs) {
    using namespace std::chrono;
    TelemetryGenerator gen("test-drone", default_sim());

    auto before_ms =
        duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
    auto pkt = gen.generate(default_pos(), ms{0});
    auto after_ms =
        duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();

    EXPECT_GE(pkt.timestamp_ms(), before_ms);
    EXPECT_LE(pkt.timestamp_ms(), after_ms);
}

// ── drone_id propagation ───────────────────────────────────────────────────────

TEST(TelemetryGenerator, DroneIdSetCorrectly) {
    TelemetryGenerator gen("cpp-drone-001", default_sim());
    auto pkt = gen.generate(default_pos(), ms{0});
    EXPECT_EQ(pkt.drone_id(), "cpp-drone-001");
}

// ── Position propagation ───────────────────────────────────────────────────────

TEST(TelemetryGenerator, PositionFieldsPopulated) {
    TelemetryGenerator gen("d", default_sim());
    Position pos{25.033, 121.565, 150.0, 12.5, 270.0};
    auto pkt = gen.generate(pos, ms{0});

    EXPECT_DOUBLE_EQ(pkt.latitude(),    25.033);
    EXPECT_DOUBLE_EQ(pkt.longitude(),   121.565);
    EXPECT_DOUBLE_EQ(pkt.altitude_m(),  150.0);
    EXPECT_DOUBLE_EQ(pkt.speed_mps(),   12.5);
    EXPECT_DOUBLE_EQ(pkt.heading_deg(), 270.0);
}

// ── Signal noise ───────────────────────────────────────────────────────────────

TEST(TelemetryGenerator, SignalStrengthWithinBounds) {
    TelemetryGenerator gen("d", default_sim());
    auto pos = default_pos();
    for (int i = 0; i < 1000; ++i) {
        auto pkt = gen.generate(pos, ms{static_cast<long long>(i) * 100});
        EXPECT_GE(pkt.signal_strength(), 0.0);
        EXPECT_LE(pkt.signal_strength(), 100.0);
    }
}
