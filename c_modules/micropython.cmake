if(NOT TARGET usermod_usb_ncm)
    # INTERFACE library — usb_ncm.c is propagated into firmware AND scanned for
    # QSTRs via MicroPython's usermod pipeline.
    #
    # Note we do NOT add lib/tinyusb/src/class/net/ncm_device.c here. The rp2
    # port links pico-sdk's tinyusb_device library, which globs all TinyUSB
    # class sources at the INTERFACE level. Once -include pico_bit_usb_config.h
    # defines CFG_TUD_NCM=1, that class driver activates itself and the linker
    # resolves it from pico-sdk's compilation, not ours. Adding it here would
    # both double-compile (duplicate symbols) and push it through the QSTR
    # preprocessor pass, which doesn't have lib/tinyusb/src on its include path.
    add_library(usermod_usb_ncm INTERFACE)

    target_sources(usermod_usb_ncm INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm/usb_ncm.c
    )

    target_include_directories(usermod_usb_ncm INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/usb_ncm
    )

    target_link_libraries(usermod INTERFACE usermod_usb_ncm)
endif()
