// src/net/http/mod.rs

mod api;
mod assets;

use picoserve::Router;
use picoserve::routing::PathRouter;

pub struct AppRouter;

impl AppRouter {
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        let router = Router::<_, ()>::new();

        let router = api::bootstrap::controller::build(router);
        let router = api::keyboard::controller::build(router);
        let router = api::armory::controller::build(router);
        let router = api::payload::controller::build(router);
        assets::build(router)
    }
}
