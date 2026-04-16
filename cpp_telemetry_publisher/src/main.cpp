#include <iostream>

// Entry point evolves across work packages:
//   WP1: print version
//   WP2: load config, print waypoints
//   WP3: send UDP protobuf packets
//   WP4: full Publisher with threading + SIGINT + CLI11 + spdlog

int main() {
    std::cout << "Telemetry Publisher v0.1\n";
    return 0;
}
