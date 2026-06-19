mod api;
mod assets;

use picoserve::Router;
use picoserve::routing::PathRouter;

pub struct AppRouter;

impl AppRouter {
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        let router = Router::<_, ()>::new();

        let router = api::build(router);
        let router = assets::build(router);

        router
    }
}
