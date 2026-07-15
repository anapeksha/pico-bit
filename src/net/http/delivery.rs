/// Fixed staged binary name shared by portal storage and NCM delivery.
pub(crate) const STAGED_BINARY_NAME: &str = "payload.bin";

/// LittleFS path containing the single NCM-deliverable binary.
pub(crate) const STAGED_BINARY_PATH: &str = "/armory/payload.bin";

/// Policy boundary for the restricted USB NCM HTTP surface.
pub(crate) struct NcmDelivery;

impl NcmDelivery {
    /// Returns whether a LittleFS path is the staged NCM binary.
    pub(crate) fn exposes_path(path: &str) -> bool {
        path == STAGED_BINARY_PATH
    }
}
