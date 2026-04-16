// main.cpp — evolves with each work package
// WP1: print version
// WP2: load config, print waypoints          ← current
// WP3: send UDP protobuf packets
// WP4: full Publisher (threading + SIGINT + CLI11 + spdlog)

#include "telemetry_publisher/config.h"
#include "telemetry_publisher/publisher.h"

#include <CLI/CLI.hpp>
#include <csignal>
#include <iostream>
#include <spdlog/spdlog.h>

namespace {
// Global publisher pointer for SIGINT handler (anonymous namespace = no true global)
tp::Publisher* g_publisher = nullptr;

void on_sigint(int /*sig*/) {
    if (g_publisher) {
        g_publisher->stop();
    }
}
}  // namespace

int main(int argc, char** argv) {
    CLI::App app{"Drone Telemetry Publisher — streams GPS telemetry via UDP/protobuf"};
    app.set_version_flag("--version", "0.1.0");

    std::string config_path;
    app.add_option("--config", config_path, "Path to YAML config file")->required();

    bool verbose = false;
    app.add_flag("--verbose,-v", verbose, "Override log level to debug");

    CLI11_PARSE(app, argc, argv);

    // ── Load config ────────────────────────────────────────────────────────────
    auto cfg_opt = tp::Config::load_from_file(config_path);
    if (!cfg_opt) {
        std::cerr << "Failed to load config: " << config_path << "\n";
        return 1;
    }
    tp::Config cfg = std::move(*cfg_opt);

    // ── Logging level ──────────────────────────────────────────────────────────
    if (verbose) {
        spdlog::set_level(spdlog::level::debug);
    } else if (cfg.publisher.log_level == "debug") {
        spdlog::set_level(spdlog::level::debug);
    } else if (cfg.publisher.log_level == "warn") {
        spdlog::set_level(spdlog::level::warn);
    } else {
        spdlog::set_level(spdlog::level::info);
    }

    spdlog::info("Telemetry Publisher v0.1 starting");
    spdlog::info("  drone_id   : {}", cfg.publisher.drone_id);
    spdlog::info("  target     : {}:{}", cfg.publisher.target_host, cfg.publisher.target_port);
    spdlog::info("  rate       : {} Hz", cfg.publisher.publish_rate_hz);
    spdlog::info("  waypoints  : {}", cfg.trajectory.waypoints.size());
    for (size_t i = 0; i < cfg.trajectory.waypoints.size(); ++i) {
        const auto& wp = cfg.trajectory.waypoints[i];
        spdlog::info("    [{}] lat={:.6f} lon={:.6f} alt={:.1f}m hold={:.1f}s",
                     i, wp.lat, wp.lon, wp.alt, wp.hold_sec);
    }

    // ── Start publisher ────────────────────────────────────────────────────────
    tp::Publisher publisher(std::move(cfg));
    g_publisher = &publisher;

    std::signal(SIGINT, on_sigint);
    std::signal(SIGTERM, on_sigint);

    publisher.start();
    publisher.wait();

    spdlog::info("Telemetry Publisher stopped cleanly");
    return 0;
}
