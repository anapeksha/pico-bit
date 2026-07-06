use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use embassy_sync::signal::Signal;
use embassy_time::Timer;

const QUEUE_DEPTH: usize = 16;

static EVENTS: Channel<CriticalSectionRawMutex, Event, QUEUE_DEPTH> = Channel::new();

/// Global signal to notify the wireless task of the physical LED state.
pub static LED_SIGNAL: Signal<CriticalSectionRawMutex, bool> = Signal::new();

/// Non-fatal firmware milestones.
#[derive(Clone, Copy)]
pub enum Stage {
    Boot,
    SetupEntered,
    SetupApStarting,
    SetupApReady,
    SetupServerReady,
    HidConstructed,
    PayloadEntered,
    UsbEnumerated,
    PayloadReady,
    PayloadRunning,
    PayloadComplete,
    BinaryInjecting,
    BinaryInjectFailed,
    KeyboardLayoutChanged,
    LootImported,
    UsbAgentMounted,
}

/// Fatal or actionable error patterns.
#[derive(Clone, Copy)]
pub enum Fault {
    UsbEnumTimeout,
    ScriptError,
    PayloadReadFailed,
    PayloadFindFailed,
    SetupApFailed,
    SetupServerFailed,
    PayloadMissing,
}

#[derive(Clone, Copy)]
enum Event {
    Stage(Stage),
    Fault(Fault),
}

#[derive(Clone, Copy)]
struct Pattern {
    count: u8,
    on_ms: u64,
    off_ms: u64,
    gap_ms: u64,
}

impl Stage {
    fn pattern(self) -> Pattern {
        match self {
            Self::Boot => Pattern::new(3, 80, 80, 0),
            Self::SetupEntered => Pattern::new(6, 400, 200, 0),
            Self::SetupApStarting => Pattern::new(1, 180, 120, 250),
            Self::SetupApReady => Pattern::new(1, 700, 0, 0),
            Self::SetupServerReady => Pattern::new(2, 220, 140, 0),
            Self::HidConstructed => Pattern::new(1, 350, 250, 600),
            Self::PayloadEntered => Pattern::new(2, 350, 250, 600),
            Self::UsbEnumerated => Pattern::new(3, 350, 250, 600),
            Self::PayloadReady => Pattern::new(4, 350, 250, 600),
            Self::PayloadRunning => Pattern::new(3, 120, 90, 180),
            Self::PayloadComplete => Pattern::new(2, 500, 300, 0),
            Self::BinaryInjecting => Pattern::new(4, 90, 70, 160),
            Self::BinaryInjectFailed => Pattern::new(5, 90, 70, 260),
            Self::KeyboardLayoutChanged => Pattern::new(3, 80, 80, 220),
            Self::LootImported => Pattern::new(3, 180, 80, 120),
            Self::UsbAgentMounted => Pattern::new(2, 80, 80, 120),
        }
    }
}

impl Fault {
    fn pattern(self) -> Pattern {
        match self {
            Self::UsbEnumTimeout => Pattern::new(1, 80, 80, 0),
            Self::ScriptError => Pattern::new(4, 350, 250, 1500),
            Self::PayloadReadFailed => Pattern::new(5, 350, 250, 1500),
            Self::PayloadFindFailed => Pattern::new(6, 350, 250, 1500),
            Self::SetupApFailed => Pattern::new(7, 350, 250, 1500),
            Self::SetupServerFailed => Pattern::new(8, 350, 250, 1500),
            Self::PayloadMissing => Pattern::new(10, 350, 250, 1500),
        }
    }
}

impl Pattern {
    const fn new(count: u8, on_ms: u64, off_ms: u64, gap_ms: u64) -> Self {
        Self {
            count,
            on_ms,
            off_ms,
            gap_ms,
        }
    }
}

/// Queue a non-fatal status pattern without blocking the caller.
pub fn show(stage: Stage) {
    let _ = EVENTS.try_send(Event::Stage(stage));
}

/// Queue a fault pattern without blocking the caller.
pub fn error(error: Fault) {
    let _ = EVENTS.try_send(Event::Fault(error));
}

/// Processes queued patterns sequentially and publishes states over `LED_SIGNAL`.
#[embassy_executor::task]
pub async fn task() {
    LED_SIGNAL.signal(true);
    Timer::after_millis(150).await;
    LED_SIGNAL.signal(false);

    loop {
        let event = EVENTS.receive().await;

        match event {
            Event::Stage(stage) => {
                play(stage.pattern()).await;
            }
            Event::Fault(error) => {
                play(error.pattern()).await;

                while let Ok(next_event) = EVENTS.try_receive() {
                    match next_event {
                        Event::Stage(s) => play(s.pattern()).await,
                        Event::Fault(f) => play(f.pattern()).await,
                    }
                }
            }
        }
    }
}

async fn play(pattern: Pattern) {
    for _ in 0..pattern.count {
        LED_SIGNAL.signal(true);
        Timer::after_millis(pattern.on_ms).await;
        LED_SIGNAL.signal(false);
        Timer::after_millis(pattern.off_ms).await;
    }

    if pattern.gap_ms > 0 {
        Timer::after_millis(pattern.gap_ms).await;
    }
}
