if(NOT TARGET usermod_usb_ncm)
    # OBJECT library: sources compile to direct .o linker inputs, NOT into an
    # archive. This ensures tud_network_recv_cb and the other TinyUSB NCM
    # callbacks are unconditionally visible at link time, regardless of the
    # order in which TinyUSB's ncm_device.c archive is scanned.
    add_library(usermod_usb_ncm OBJECT
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm/usb_ncm.c
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm/usb_ncm_descriptors.c
    )

    # Inherit MicroPython/TinyUSB/lwIP include paths from usermod at build
    # time via generator expression (evaluated during make, not cmake).
    target_include_directories(usermod_usb_ncm PRIVATE
        $<TARGET_PROPERTY:usermod,INTERFACE_INCLUDE_DIRECTORIES>
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm
    )

    # Add the compiled object files directly to any target that links usermod.
    target_link_libraries(usermod INTERFACE
        $<TARGET_OBJECTS:usermod_usb_ncm>
    )
    target_include_directories(usermod INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm
    )
endif()
