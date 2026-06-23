// src/net/http/mod.rs

mod api;
mod assets;

use picoserve::Router;
use picoserve::routing::PathRouter;

pub struct AppRouter;

impl AppRouter {
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        let router = Router::<_, ()>::new();

        let router = api::status::build(router);
        let router = api::payload::build(router); // Type matches () state perfectly now
        assets::build(router)
    }
}
