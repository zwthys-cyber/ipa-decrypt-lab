#include <apple_auth/testflight.hpp>
#include <array>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace apple_auth;
template<class F> void rejects(F operation) {
    bool rejected=false;
    try { operation(); } catch (const std::exception&) { rejected=true; }
    if (!rejected) throw std::runtime_error("invalid input accepted");
}
int main() {
    try {
        // Invalid persisted sessions must never reach the injected transport.
        unsigned calls=0;
        Transport transport=[&calls](const HttpRequest&) -> HttpResponse {
            ++calls; throw std::runtime_error("unexpected network request");
        };
        const std::string invalid="{}";
        ByteView json(reinterpret_cast<const std::uint8_t*>(invalid.data()),invalid.size());
        rejects([&] { TestFlightClient client(json,transport); });
        if(calls) throw std::runtime_error("invalid session attempted network");
        std::array<std::uint8_t,20> hardware{};
        std::array<std::uint8_t,88> info{};
        rejects([&] { TestFlightTransport value(ByteView(hardware).first(19),info); });
        rejects([&] { TestFlightTransport value(hardware,ByteView(info).first(87)); });
        rejects([&] { generate_kbsync(1,ByteView(hardware).first(19)); });
        std::cout << "synthetic session and transport guards passed\n";
        return 0;
    } catch (...) { std::cerr << "synthetic contract failed\n"; return 1; }
}
