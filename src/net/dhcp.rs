use embassy_net::Ipv4Address;
use leasehund::{DhcpConfigBuilder, DhcpServer};

pub fn init_usb_dhcp() -> DhcpServer<32, 4> {
    let config = DhcpConfigBuilder::new()
        .server_ip(Ipv4Address::new(192, 168, 7, 1))
        .subnet_mask(Ipv4Address::new(255, 255, 255, 0))
        .router(Ipv4Address::new(192, 168, 7, 1))
        .ip_pool(
            Ipv4Address::new(192, 168, 7, 2),
            Ipv4Address::new(192, 168, 7, 2),
        )
        .add_dns_server(Ipv4Address::new(1, 1, 1, 1))
        .add_dns_server(Ipv4Address::new(1, 0, 0, 1))
        .add_dns_server(Ipv4Address::new(8, 8, 8, 8))
        .lease_time(7200)
        .build();

    DhcpServer::<32, 4>::with_config(config)
}

pub fn init_wifi_dhcp() -> DhcpServer<32, 4> {
    let config = DhcpConfigBuilder::new()
        .server_ip(Ipv4Address::new(192, 168, 4, 1))
        .subnet_mask(Ipv4Address::new(255, 255, 255, 0))
        .router(Ipv4Address::new(192, 168, 4, 1))
        .ip_pool(
            Ipv4Address::new(192, 168, 4, 2),
            Ipv4Address::new(192, 168, 4, 254),
        )
        .add_dns_server(Ipv4Address::new(1, 1, 1, 1))
        .add_dns_server(Ipv4Address::new(1, 0, 0, 1))
        .add_dns_server(Ipv4Address::new(8, 8, 8, 8))
        .lease_time(7200)
        .build();

    DhcpServer::<32, 4>::with_config(config)
}
