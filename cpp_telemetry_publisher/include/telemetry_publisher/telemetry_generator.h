#pragma once

#include "telemetry_publisher/config.h"
#include "telemetry_publisher/trajectory.h"

// Forward-declare the generated protobuf type to keep compile times low
namespace drone_platform::telemetry { class TelemetryPacket; }

#include <chrono>
#include <cstdint>
#include <random>
#include <string>

namespace tp {

/// Converts a raw Position into a fully-populated TelemetryPacket.
///
/// Responsibilities:
/// - Assigns drone_id and auto-incrementing sequence number
/// - Computes battery drain linearly with elapsed time
/// - Adds Gaussian noise to signal strength
/// - Stamps packets with the current wall-clock time (milliseconds since epoch)
class TelemetryGenerator {
public:
    TelemetryGenerator(std::string drone_id, SimulationConfig sim_config);

    /// Build a TelemetryPacket from the given position.
    /// elapsed is the total simulation time so far (for battery drain).
    drone_platform::telemetry::TelemetryPacket
    generate(const Position& pos, std::chrono::milliseconds elapsed);

private:
    std::string      drone_id_;
    SimulationConfig sim_config_;
    uint32_t         sequence_{0};
    std::mt19937     rng_;
};

}  // namespace tp
