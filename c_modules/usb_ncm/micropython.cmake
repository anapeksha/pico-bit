add_library(usermod_usb_ncm INTERFACE)

target_sources(usermod_usb_ncm INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/usb_ncm.c
    ${CMAKE_CURRENT_LIST_DIR}/usb_ncm_descriptors.c
)

target_include_directories(usermod_usb_ncm INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(usermod INTERFACE usermod_usb_ncm)
