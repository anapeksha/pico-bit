use embassy_rp::{peripherals::USB, usb::Driver};
use embassy_usb::class::cdc_ncm::{
    CdcNcmClass, State as NcmState,
    embassy_net::{Device as NetDevice, Runner as NetRunner, State as NetState},
};
use embassy_usb::class::hid::State as HidState;
use embassy_usb::class::hid::{Config as HidConfig, HidBootProtocol, HidSubclass, HidWriter};
use embassy_usb::{Builder, Config as UsbConfig, UsbDevice};
use static_cell::StaticCell;
use usbd_hid::descriptor::{KeyboardReport, SerializedDescriptor};

const MTU: usize = 1514;
const N_RX: usize = 2;
const N_TX: usize = 2;

static HID_STATIC: StaticCell<HidState> = StaticCell::new();
static CONFIG_DESCRIPTOR_BUF: StaticCell<[u8; 1024]> = StaticCell::new();
static BOS_DESCRIPTOR_BUF: StaticCell<[u8; 256]> = StaticCell::new();
static MSOS_DESCRIPTOR_BUF: StaticCell<[u8; 256]> = StaticCell::new();
static CONTROL_BUF: StaticCell<[u8; 64]> = StaticCell::new();
static NCM_STATIC: StaticCell<NcmState> = StaticCell::new();
static NET_STATE: StaticCell<NetState<MTU, N_RX, N_TX>> = StaticCell::new();

pub struct UsbManager {
    pub device: UsbDevice<'static, Driver<'static, USB>>,
    pub hid: HidWriter<'static, Driver<'static, USB>, 8>,
    pub net_runner: NetRunner<'static, Driver<'static, USB>, MTU>,
    pub net_device: NetDevice<'static, MTU>,
}

impl UsbManager {
    pub fn new(driver: Driver<'static, USB>) -> Self {
        let mut usb_config = UsbConfig::new(0x0001, 0x0001);

        usb_config.manufacturer = Some("Pico Bit");
        usb_config.product = Some("Pico Bit");
        usb_config.serial_number = Some("12345");
        usb_config.device_class = 0xEF; // Miscellaneous Device Class
        usb_config.device_sub_class = 0x02; // Common Class
        usb_config.device_protocol = 0x01; // Interface Association Descriptor (IAD)
        usb_config.composite_with_iads = true; // Force the USB builder to emit IAD headers

        let mut builder = Builder::new(
            driver,
            usb_config,
            CONFIG_DESCRIPTOR_BUF.init([0; 1024]),
            BOS_DESCRIPTOR_BUF.init([0; 256]),
            MSOS_DESCRIPTOR_BUF.init([0; 256]),
            CONTROL_BUF.init([0; 64]),
        );

        let hid_state = HID_STATIC.init(HidState::new());
        let hid_config = HidConfig {
            report_descriptor: KeyboardReport::desc(),
            hid_subclass: HidSubclass::Boot,
            hid_boot_protocol: HidBootProtocol::Keyboard,
            poll_ms: 60,
            max_packet_size: 8,
            request_handler: None,
        };
        let hid = HidWriter::new(&mut builder, hid_state, hid_config);

        let ncm_state = NCM_STATIC.init(NcmState::new());

        let mac_pico = [0x02, 0x00, 0x00, 0x00, 0x00, 0x01];
        let mac_host = [0x02, 0x00, 0x00, 0x00, 0x00, 0x02];

        let ncm = CdcNcmClass::new(&mut builder, ncm_state, mac_host, 64);

        let net_state = NET_STATE.init(NetState::new());
        let (net_runner, net_device) =
            ncm.into_embassy_net_device::<MTU, N_RX, N_TX>(net_state, mac_pico);

        let device = builder.build();

        Self {
            device,
            hid,
            net_runner,
            net_device,
        }
    }
}
