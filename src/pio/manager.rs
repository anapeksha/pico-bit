use cyw43_pio::{PioSpi, RM2_CLOCK_DIVIDER};
use embassy_rp::{
    Peri,
    dma::Channel,
    gpio::{Level, Output},
    peripherals::{DMA_CH0, PIN_23, PIN_24, PIN_25, PIN_29, PIO0},
    pio::Pio,
};

use crate::Irqs;

/// CYW43 PIO/SPI resources required by the Wi-Fi runner.
pub struct PioManager {
    /// PIO SPI bus connected to the wireless chip.
    pub spi: PioSpi<'static, PIO0, 0>,
    /// Wireless chip power control pin.
    pub pwr: Output<'static>,
}

impl PioManager {
    /// Claims PIO, pins, and DMA resources for the CYW43 bus.
    pub fn new(
        mut pio: Pio<'static, PIO0>,
        pin_23: Peri<'static, PIN_23>,   // WL_ON
        pin_24: Peri<'static, PIN_24>,   // WL_DIO
        pin_25: Peri<'static, PIN_25>,   // WL_CLK
        pin_29: Peri<'static, PIN_29>,   // WL_CS
        dma_ch0: Peri<'static, DMA_CH0>, // Single DMA channel token
        irqs: Irqs,
    ) -> Self {
        let pwr = Output::new(pin_23, Level::Low);
        let cs = Output::new(pin_25, Level::High);

        let spi = PioSpi::new(
            &mut pio.common,
            pio.sm0,
            RM2_CLOCK_DIVIDER,
            pio.irq0,
            cs,
            pin_24,
            pin_29,
            Channel::new(dma_ch0, irqs),
        );

        Self { spi, pwr }
    }
}
