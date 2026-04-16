#include "telemetry_publisher/udp_socket.h"

#include <arpa/inet.h>
#include <stdexcept>
#include <unistd.h>

#include <spdlog/spdlog.h>

namespace tp {

UdpSocket::UdpSocket(const std::string& host, uint16_t port) {
    fd_ = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (fd_ < 0) {
        throw std::runtime_error("Failed to create UDP socket");
    }

    target_.sin_family = AF_INET;
    target_.sin_port   = htons(port);
    if (::inet_pton(AF_INET, host.c_str(), &target_.sin_addr) != 1) {
        ::close(fd_);
        fd_ = -1;
        throw std::runtime_error("Invalid target host: " + host);
    }

    spdlog::debug("UdpSocket opened fd={} → {}:{}", fd_, host, port);
}

UdpSocket::~UdpSocket() {
    if (fd_ >= 0) {
        ::close(fd_);
        spdlog::debug("UdpSocket fd={} closed", fd_);
        fd_ = -1;
    }
}

UdpSocket::UdpSocket(UdpSocket&& other) noexcept
    : fd_(other.fd_), target_(other.target_) {
    other.fd_ = -1;
}

UdpSocket& UdpSocket::operator=(UdpSocket&& other) noexcept {
    if (this != &other) {
        if (fd_ >= 0) ::close(fd_);
        fd_       = other.fd_;
        target_   = other.target_;
        other.fd_ = -1;
    }
    return *this;
}

ssize_t UdpSocket::send(const std::vector<uint8_t>& data) {
    if (fd_ < 0) {
        spdlog::error("UdpSocket::send called on closed socket");
        return -1;
    }
    ssize_t sent = ::sendto(
        fd_,
        data.data(),
        data.size(),
        0,
        reinterpret_cast<const sockaddr*>(&target_),
        sizeof(target_));

    if (sent < 0) {
        spdlog::error("UdpSocket::send failed: {}", ::strerror(errno));
    }
    return sent;
}

bool UdpSocket::is_open() const { return fd_ >= 0; }

}  // namespace tp
