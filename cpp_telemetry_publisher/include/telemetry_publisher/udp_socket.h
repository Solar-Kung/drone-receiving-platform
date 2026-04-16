#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <netinet/in.h>

namespace tp {

/// RAII wrapper for a non-blocking UDP send socket.
///
/// Demonstrates:
/// - RAII: constructor opens fd, destructor closes it (no leaks even on exception)
/// - Move semantics: ownership of fd can be transferred; copy is disabled
/// - No raw new/delete
class UdpSocket {
public:
    /// Open a UDP socket targeting host:port.
    /// Throws std::runtime_error if the socket cannot be created.
    UdpSocket(const std::string& host, uint16_t port);

    /// Closes the fd if still open.
    ~UdpSocket();

    // Non-copyable — fd ownership is exclusive
    UdpSocket(const UdpSocket&)            = delete;
    UdpSocket& operator=(const UdpSocket&) = delete;

    /// Transfer ownership of the fd; the moved-from object becomes invalid.
    UdpSocket(UdpSocket&& other) noexcept;
    UdpSocket& operator=(UdpSocket&& other) noexcept;

    /// Send raw bytes.  Returns bytes sent on success, -1 on error (logged internally).
    ssize_t send(const std::vector<uint8_t>& data);

    /// True if the socket fd is valid.
    bool is_open() const;

private:
    int         fd_{-1};
    sockaddr_in target_{};
};

}  // namespace tp
