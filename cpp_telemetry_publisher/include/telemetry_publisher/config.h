#pragma once

#include <optional>
#include <string>
#include <vector>

namespace tp {

/// A single GPS waypoint with an optional hover duration.
struct Waypoint {
    double lat{};
    double lon{};
    double alt{};
    double hold_sec{};
};

struct PublisherConfig {
    std::string drone_id;
    std::string target_host;
    uint16_t    target_port{14550};
    int         publish_rate_hz{10};
    std::string log_level{"info"};
};

struct TrajectoryConfig {
    std::vector<Waypoint> waypoints;
    double speed_mps{10.0};
};

struct SimulationConfig {
    double battery_drain_per_second{0.05};
    double signal_base{95.0};
    double signal_noise{5.0};
    bool   loop{true};
};

/// Top-level configuration loaded from a YAML file.
struct Config {
    PublisherConfig  publisher;
    TrajectoryConfig trajectory;
    SimulationConfig simulation;

    /// Parse a YAML file and return Config on success, nullopt on any error.
    static std::optional<Config> load_from_file(const std::string& path);
};

}  // namespace tp
