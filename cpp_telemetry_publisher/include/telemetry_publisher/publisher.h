#pragma once

#include "telemetry_publisher/config.h"
#include "telemetry_publisher/telemetry_generator.h"
#include "telemetry_publisher/trajectory.h"
#include "telemetry_publisher/udp_socket.h"

// Generated protobuf type
namespace drone_platform::telemetry { class TelemetryPacket; }

#include <atomic>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <queue>
#include <thread>

namespace tp {

/// Integrates Trajectory, TelemetryGenerator, and UdpSocket into a
/// producer-consumer publishing pipeline.
///
/// Threading model:
///   generator_thread  — wakes at publish_rate_hz, calls Trajectory::advance +
///                       TelemetryGenerator::generate, pushes to queue_
///   publisher_thread  — blocks on queue_, serialises the protobuf packet,
///                       sends via UdpSocket
///
/// The two threads are decoupled so network I/O never blocks telemetry generation.
class Publisher {
public:
    explicit Publisher(Config config);
    ~Publisher();

    /// Start both worker threads.
    void start();

    /// Signal worker threads to stop (sets running_ = false).
    void stop();

    /// Block until both threads have joined (call after stop()).
    void wait();

private:
    void generator_loop();
    void publisher_loop();

    Config config_;

    std::atomic<bool> running_{false};

    // Producer-consumer queue (protobuf packets awaiting UDP send)
    std::queue<drone_platform::telemetry::TelemetryPacket> queue_;
    std::mutex                                              queue_mutex_;
    std::condition_variable                                 queue_cv_;
    static constexpr size_t kMaxQueueSize = 100;

    std::thread generator_thread_;
    std::thread publisher_thread_;

    // Owned resources — unique_ptr for RAII, no raw new/delete
    std::unique_ptr<UdpSocket>          socket_;
    std::unique_ptr<Trajectory>         trajectory_;
    std::unique_ptr<TelemetryGenerator> generator_;
};

}  // namespace tp
