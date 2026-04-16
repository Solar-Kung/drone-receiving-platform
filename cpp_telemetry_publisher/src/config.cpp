#include "telemetry_publisher/config.h"

#include <iostream>
#include <yaml-cpp/yaml.h>

namespace tp {

std::optional<Config> Config::load_from_file(const std::string& path) {
    try {
        YAML::Node root = YAML::LoadFile(path);

        Config cfg;

        // ── publisher ──────────────────────────────────────────────────────────
        auto pub = root["publisher"];
        cfg.publisher.drone_id        = pub["drone_id"].as<std::string>();
        cfg.publisher.target_host     = pub["target_host"].as<std::string>();
        cfg.publisher.target_port     = pub["target_port"].as<uint16_t>();
        cfg.publisher.publish_rate_hz = pub["publish_rate_hz"].as<int>();
        cfg.publisher.log_level       = pub["log_level"].as<std::string>("info");

        // ── trajectory ────────────────────────────────────────────────────────
        auto traj = root["trajectory"];
        cfg.trajectory.speed_mps = traj["speed_mps"].as<double>();
        for (const auto& wp : traj["waypoints"]) {
            cfg.trajectory.waypoints.push_back({
                wp["lat"].as<double>(),
                wp["lon"].as<double>(),
                wp["alt"].as<double>(),
                wp["hold_sec"].as<double>(0.0),
            });
        }

        // ── simulation ────────────────────────────────────────────────────────
        auto sim = root["simulation"];
        cfg.simulation.battery_drain_per_second =
            sim["battery_drain_per_second"].as<double>();
        cfg.simulation.signal_base  = sim["signal_base"].as<double>();
        cfg.simulation.signal_noise = sim["signal_noise"].as<double>();
        cfg.simulation.loop         = sim["loop"].as<bool>(true);

        return cfg;

    } catch (const YAML::Exception& e) {
        std::cerr << "[Config] YAML error: " << e.what() << "\n";
        return std::nullopt;
    } catch (const std::exception& e) {
        std::cerr << "[Config] Error loading " << path << ": " << e.what() << "\n";
        return std::nullopt;
    }
}

}  // namespace tp
