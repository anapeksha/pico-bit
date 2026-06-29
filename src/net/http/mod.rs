mod api;
mod assets;

use picoserve::Router;
use picoserve::routing::PathRouter;

use crate::ducky::KeyboardLayout;

pub struct AppRouter;

pub(crate) fn active_keyboard_layout() -> KeyboardLayout {
    api::keyboard::service::active_layout()
}

pub(crate) fn active_keyboard_target_codes() -> (&'static str, &'static str) {
    api::keyboard::service::active_target_codes()
}

pub(crate) fn update_keyboard_target_codes(os: &str, layout: &str) -> bool {
    api::keyboard::service::update_target_codes(os, layout)
}

pub(crate) fn compressed_index_html() -> &'static [u8] {
    assets::compressed_index_html()
}

impl AppRouter {
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        let router = Router::<_, ()>::new();

        let router = api::bootstrap::controller::build(router);
        let router = api::keyboard::controller::build(router);
        let router = api::armory::controller::build(router);
        let router = api::payload::controller::build(router);
        let router = api::runs::controller::build(router);
        assets::build(router)
    }
}
