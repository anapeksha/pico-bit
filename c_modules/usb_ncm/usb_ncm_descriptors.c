/*
 * USB composite descriptor: HID keyboard + MSC + CDC-NCM.
 *
 * Overrides the weak tud_descriptor_device_cb() and
 * tud_descriptor_configuration_cb() symbols from TinyUSB so the host sees
 * all three interfaces under one composite device with IAD grouping for NCM.
 *
 * Endpoint layout:
 *   EP0        control (always)
 *   EP1 IN/OUT MSC bulk         (MicroPython builtin)
 *   EP2 IN     HID interrupt    (machine.USBDevice runtime — starts at USBD_EP_BUILTIN_MAX=5,
 *                                but the runtime picks the first free EP after builtins;
 *                                with USBD_EP_BUILTIN_MAX=5 it will use EP5 for HID)
 *   EP3 IN     NCM notification interrupt
 *   EP4 IN     NCM bulk data IN (double-buffered)
 *   EP4 OUT    NCM bulk data OUT(double-buffered)
 *
 * USBD_EP_BUILTIN_MAX is set to 5 in pico_bit_usb_config.h so machine.USBDevice
 * cannot claim EP3 or EP4 before the NCM module registers them.
 */

#include "tusb.h"
#include "class/hid/hid_device.h"
#include "class/msc/msc_device.h"
#include "class/net/ncm.h"

/* ---- string indices ---- */
#define STR_MANUF       1
#define STR_PRODUCT     2
#define STR_SERIAL      3
#define STR_MSC         4
#define STR_NCM         5

/* ---- endpoint numbers ---- */
#define EP_MSC_OUT      0x01
#define EP_MSC_IN       0x81
#define EP_HID_IN       0x82   /* HID assigned by machine.USBDevice runtime */
#define EP_NCM_NOTIF    0x83
#define EP_NCM_OUT      0x04
#define EP_NCM_IN       0x84

/* ---- interface numbers ---- */
#define ITF_MSC         0
#define ITF_NCM_COMM    1
#define ITF_NCM_DATA    2
#define ITF_TOTAL       3

/* ---- HID report descriptor: 6-key boot keyboard ---- */
static const uint8_t _hid_report_desc[] = {
    TUD_HID_REPORT_DESC_KEYBOARD()
};

uint16_t tud_hid_get_report_cb(uint8_t itf, uint8_t report_id,
                                hid_report_type_t report_type,
                                uint8_t *buffer, uint16_t reqlen) {
    (void)itf; (void)report_id; (void)report_type; (void)buffer; (void)reqlen;
    return 0;
}

void tud_hid_set_report_cb(uint8_t itf, uint8_t report_id,
                            hid_report_type_t report_type,
                            const uint8_t *buffer, uint16_t bufsize) {
    (void)itf; (void)report_id; (void)report_type; (void)buffer; (void)bufsize;
}

uint8_t const *tud_hid_descriptor_report_cb(uint8_t itf) {
    (void)itf;
    return _hid_report_desc;
}

/* ---- device descriptor ---- */
static const tusb_desc_device_t _desc_device = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0200,
    /* composite device with IAD */
    .bDeviceClass       = TUSB_CLASS_MISC,
    .bDeviceSubClass    = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol    = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor           = 0x2E8A,   /* Raspberry Pi */
    .idProduct          = 0x000A,
    .bcdDevice          = 0x0100,
    .iManufacturer      = STR_MANUF,
    .iProduct           = STR_PRODUCT,
    .iSerialNumber      = STR_SERIAL,
    .bNumConfigurations = 1,
};

uint8_t const *tud_descriptor_device_cb(void) {
    return (uint8_t const *)&_desc_device;
}

/* ---- configuration descriptor ---- */
/*
 * Total length:
 *   9  config header
 *   9  MSC interface
 *   7  MSC endpoint IN
 *   7  MSC endpoint OUT
 *   8  IAD for NCM (2 interfaces)
 *   9  CDC comm interface
 *   5  CDC header functional
 *   5  CDC union functional
 *   13 NCM functional
 *   7  NCM notification endpoint
 *   9  CDC data interface (alt 0, no endpoints)
 *   9  CDC data interface (alt 1, with endpoints)
 *   7  NCM bulk OUT endpoint
 *   7  NCM bulk IN endpoint
 * = 109 bytes
 */
#define CONFIG_TOTAL_LEN  (TUD_CONFIG_DESC_LEN + TUD_MSC_DESC_LEN + TUD_CDC_NCM_DESC_LEN)

static const uint8_t _desc_configuration[] = {
    /* Config header */
    TUD_CONFIG_DESCRIPTOR(1, ITF_TOTAL, 0, CONFIG_TOTAL_LEN,
                          TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP, 250),

    /* MSC — interface 0 */
    TUD_MSC_DESCRIPTOR(ITF_MSC, STR_MSC, EP_MSC_OUT, EP_MSC_IN,
                       CFG_TUD_MSC_BUFSIZE),

    /* CDC-NCM — interfaces 1 (comm) + 2 (data), wrapped in IAD */
    TUD_CDC_NCM_DESCRIPTOR(ITF_NCM_COMM, STR_NCM, EP_NCM_NOTIF, 64,
                           EP_NCM_OUT, EP_NCM_IN, CFG_TUD_NCM_EP_BUFSIZE,
                           CFG_TUD_NCM_NTBSIZE),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return _desc_configuration;
}

/* ---- string descriptor ---- */
static const char *_string_desc[] = {
    "\x09\x04",         /* 0: language = English */
    "Pico Bit",         /* 1: manufacturer */
    "Pico Bit",         /* 2: product */
    NULL,               /* 3: serial — filled at runtime by mp_usbd_port_get_serial_number */
    "Pico Bit MSC",     /* 4: MSC interface */
    "Pico Bit NCM",     /* 5: NCM interface */
};

static uint16_t _desc_str[32];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    uint8_t chr_count;
    if (index == 0) {
        memcpy(&_desc_str[1], _string_desc[0], 2);
        chr_count = 1;
    } else if (index < sizeof(_string_desc) / sizeof(_string_desc[0])) {
        const char *str = _string_desc[index];
        if (!str) return NULL;
        chr_count = (uint8_t)strlen(str);
        if (chr_count > 31) chr_count = 31;
        for (uint8_t i = 0; i < chr_count; i++) {
            _desc_str[1 + i] = str[i];
        }
    } else {
        return NULL;
    }
    _desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));
    return _desc_str;
}
