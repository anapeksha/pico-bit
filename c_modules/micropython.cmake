if(NOT TARGET usermod_usb_ncm)
    # INTERFACE library — sources are propagated into firmware AND scanned for
    # QSTRs via MicroPython's usermod pipeline. MICROPY_DIR is set by the rp2
    # port's top-level CMakeLists.txt and resolves to the micropython checkout
    # under .build/micropython.
    add_library(usermod_usb_ncm INTERFACE)

    target_sources(usermod_usb_ncm INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm/usb_ncm.c
        # TinyUSB's NCM class driver isn't in MicroPython's TinyUSB compile list
        # (which only includes CDC/HID/MSC). Pull it in here so the linker can
        # resolve ncmd_init / ncmd_open / ncmd_xfer_cb that tusb.c references
        # once CFG_TUD_NCM=1 enters the class driver table.
        ${MICROPY_DIR}/lib/tinyusb/src/class/net/ncm_device.c
    )

    target_include_directories(usermod_usb_ncm INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm
    )

    target_link_libraries(usermod INTERFACE usermod_usb_ncm)
endif()
