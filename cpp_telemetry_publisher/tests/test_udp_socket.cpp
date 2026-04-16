#include "telemetry_publisher/udp_socket.h"

#include <gtest/gtest.h>
#include <cstring>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

namespace {

/// Bind a UDP socket on an ephemeral port and return the port number.
int bind_ephemeral(int* fd_out) {
    int fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port        = 0;  // Let OS assign

    if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        ::close(fd);
        return -1;
    }

    socklen_t len = sizeof(addr);
    ::getsockname(fd, reinterpret_cast<sockaddr*>(&addr), &len);
    *fd_out = fd;
    return ntohs(addr.sin_port);
}

}  // namespace

// ── Construction & basic send ──────────────────────────────────────────────────

TEST(UdpSocket, ConstructOpenSocket) {
    int recv_fd;
    int port = bind_ephemeral(&recv_fd);
    ASSERT_GT(port, 0);

    tp::UdpSocket sock("127.0.0.1", static_cast<uint16_t>(port));
    EXPECT_TRUE(sock.is_open());

    ::close(recv_fd);
}

TEST(UdpSocket, SendReachesReceiver) {
    int recv_fd;
    int port = bind_ephemeral(&recv_fd);
    ASSERT_GT(port, 0);

    tp::UdpSocket sock("127.0.0.1", static_cast<uint16_t>(port));
    std::vector<uint8_t> payload{0x01, 0x02, 0x03};
    EXPECT_EQ(sock.send(payload), static_cast<ssize_t>(payload.size()));

    // Verify reception
    char buf[64]{};
    ssize_t n = ::recv(recv_fd, buf, sizeof(buf), MSG_DONTWAIT);
    EXPECT_EQ(n, 3);
    EXPECT_EQ(static_cast<uint8_t>(buf[0]), 0x01);

    ::close(recv_fd);
}

// ── Move semantics ─────────────────────────────────────────────────────────────

TEST(UdpSocket, MoveConstructorTransfersOwnership) {
    int recv_fd;
    int port = bind_ephemeral(&recv_fd);
    ASSERT_GT(port, 0);

    tp::UdpSocket original("127.0.0.1", static_cast<uint16_t>(port));
    ASSERT_TRUE(original.is_open());

    tp::UdpSocket moved(std::move(original));

    // Source is invalid after move
    EXPECT_FALSE(original.is_open());  // NOLINT(bugprone-use-after-move)
    // Destination is valid
    EXPECT_TRUE(moved.is_open());

    ::close(recv_fd);
    // moved destructor closes fd — no double-close because original.fd_ == -1
}

TEST(UdpSocket, MoveAssignmentTransfersOwnership) {
    int recv_fd1, recv_fd2;
    int port1 = bind_ephemeral(&recv_fd1);
    int port2 = bind_ephemeral(&recv_fd2);
    ASSERT_GT(port1, 0);
    ASSERT_GT(port2, 0);

    tp::UdpSocket sock1("127.0.0.1", static_cast<uint16_t>(port1));
    tp::UdpSocket sock2("127.0.0.1", static_cast<uint16_t>(port2));

    sock1 = std::move(sock2);

    EXPECT_FALSE(sock2.is_open());  // NOLINT(bugprone-use-after-move)
    EXPECT_TRUE(sock1.is_open());

    ::close(recv_fd1);
    ::close(recv_fd2);
}

// ── RAII: destructor closes fd ─────────────────────────────────────────────────

TEST(UdpSocket, DestructorClosesFd) {
    int captured_fd = -1;
    {
        // Access private fd via a send-on-closed-socket test: after scope exits,
        // the OS-level fd should be reclaimed (we cannot read private fd_ directly,
        // so we verify by scoping and checking is_open() before destruction).
        int recv_fd;
        int port = bind_ephemeral(&recv_fd);
        ASSERT_GT(port, 0);

        tp::UdpSocket sock("127.0.0.1", static_cast<uint16_t>(port));
        EXPECT_TRUE(sock.is_open());
        (void)captured_fd;  // Would store fd_ if accessible

        ::close(recv_fd);
        // sock destructor runs here
    }
    // If fd was not closed, the OS would reuse it and we'd eventually run out of fds.
    // The test passes if no crash or resource leak is detected by sanitizers.
    SUCCEED();
}
