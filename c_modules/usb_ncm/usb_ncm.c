#include "tusb_option.h"
#if CFG_TUD_NCM

/*
 * usb_ncm — MicroPython C module for USB CDC-NCM Ethernet.
 *
 * Wires TinyUSB CDC-NCM callbacks into lwIP as a second netif alongside
 * the CYW43 Wi-Fi AP.  Exposes three Python callables:
 *
 *   usb_ncm.init(ip, netmask, gateway)  — register netif, start DHCP server
 *   usb_ncm.poll()                      — drive tud_task() + process NCM events
 *   usb_ncm.is_ready()                  — True once host has opened the NCM interface
 *
 * Performance notes:
 *   - RX frames allocated from PBUF_POOL (pre-allocated, zero heap churn)
 *   - tud_network_recv_renew() called immediately to keep USB RX pipeline full
 *   - DMA bulk transfers used by TinyUSB automatically on RP2350
 *   - poll() is non-blocking; called from the asyncio loop every 10 ms
 */

#include <stdlib.h>
#include <string.h>

#include "py/runtime.h"
#include "py/obj.h"

#include "tusb.h"
#include "lwip/netif.h"
#include "lwip/etharp.h"
#include "lwip/pbuf.h"
#include "lwip/ip4_addr.h"
#include "lwip/tcpip.h"
#include "netif/ethernet.h"
#include "shared/netutils/dhcpserver.h"  /* MicroPython DHCP server, compiled for CYW43 AP */

/* ---- module state ---- */
static struct netif _ncm_netif;
static dhcp_server_t _ncm_dhcp_server;
static bool _ncm_ready = false;
static volatile bool _ncm_init_pending = false;

/* MAC derived from board unique ID at init time */
static uint8_t _mac[6];

/* ---- helpers ---- */
static void _derive_mac(void) {
    /* Use the lower 6 bytes of the RP2350 unique board ID.
       Set the locally-administered bit and clear multicast. */
    extern void mp_usbd_port_get_serial_number(char *buf);
    char serial[20] = {0};
    mp_usbd_port_get_serial_number(serial);
    /* serial is hex ASCII; parse last 12 chars as 6 bytes */
    const char *s = serial + (strlen(serial) > 12 ? strlen(serial) - 12 : 0);
    for (int i = 0; i < 6; i++) {
        char byte_str[3] = {s[i * 2], s[i * 2 + 1], 0};
        _mac[i] = (uint8_t)strtol(byte_str, NULL, 16);
    }
    _mac[0] = (_mac[0] & 0xFE) | 0x02; /* locally administered, unicast */
}

/* ---- lwIP netif callbacks ---- */
static err_t _ncm_netif_linkoutput(struct netif *netif, struct pbuf *p) {
    (void)netif;
    if (!tud_ready()) return ERR_IF;
    /* tud_network_xmit queues the pbuf for TinyUSB DMA transmit */
    tud_network_xmit(p, 0);
    return ERR_OK;
}

static err_t _ncm_netif_init(struct netif *netif) {
    netif->name[0] = 'u';
    netif->name[1] = '0';
    netif->output     = etharp_output;
    netif->linkoutput = _ncm_netif_linkoutput;
    netif->mtu        = 1514;
    netif->hwaddr_len = 6;
    memcpy(netif->hwaddr, _mac, 6);
    netif->flags = NETIF_FLAG_BROADCAST | NETIF_FLAG_ETHARP | NETIF_FLAG_LINK_UP;
    return ERR_OK;
}

/* ---- TinyUSB NCM callbacks (called from USB IRQ) ---- */

void tud_network_init_cb(void) {
    /* Host opened the NCM interface — signal the poll loop to complete setup */
    _ncm_init_pending = true;
}

bool tud_network_recv_cb(const uint8_t *src, uint16_t size) {
    struct pbuf *p = pbuf_alloc(PBUF_RAW, size, PBUF_POOL);
    if (p) {
        pbuf_take(p, src, size);
        if (_ncm_netif.input(p, &_ncm_netif) != ERR_OK) {
            pbuf_free(p);
        }
    }
    /* Renew immediately so TinyUSB can accept the next frame without stalling */
    tud_network_recv_renew();
    return true;
}

uint16_t tud_network_xmit_cb(uint8_t *dst, void *ref, uint16_t arg) {
    (void)arg;
    struct pbuf *p = (struct pbuf *)ref;
    uint16_t len = 0;
    for (struct pbuf *q = p; q != NULL; q = q->next) {
        memcpy(dst + len, q->payload, q->len);
        len += q->len;
    }
    return len;
}

/* ---- complete NCM init on first poll after host opens interface ---- */
static void _complete_ncm_init(void) {
    if (!_ncm_init_pending) return;
    _ncm_init_pending = false;
    netif_set_link_up(&_ncm_netif);
    _ncm_ready = true;
}

/* ---- Python API ---- */

static mp_obj_t py_usb_ncm_init(mp_obj_t ip_obj, mp_obj_t nm_obj, mp_obj_t gw_obj) {
    const char *ip_str = mp_obj_str_get_str(ip_obj);
    const char *nm_str = mp_obj_str_get_str(nm_obj);
    const char *gw_str = mp_obj_str_get_str(gw_obj);

    ip4_addr_t ip, netmask, gateway;
    if (!ip4addr_aton(ip_str, &ip) ||
        !ip4addr_aton(nm_str, &netmask) ||
        !ip4addr_aton(gw_str, &gateway)) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid IP address"));
    }

    _derive_mac();

    netif_add(&_ncm_netif, &ip, &netmask, &gateway,
              NULL, _ncm_netif_init, netif_input);
    netif_set_up(&_ncm_netif);

    /* Start MicroPython DHCP server (same one used by CYW43 AP mode) */
    dhcp_server_init(&_ncm_dhcp_server, &ip, &netmask);

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(py_usb_ncm_init_obj, py_usb_ncm_init);

static mp_obj_t py_usb_ncm_poll(void) {
    tud_task();
    _complete_ncm_init();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(py_usb_ncm_poll_obj, py_usb_ncm_poll);

static mp_obj_t py_usb_ncm_is_ready(void) {
    return mp_obj_new_bool(_ncm_ready);
}
static MP_DEFINE_CONST_FUN_OBJ_0(py_usb_ncm_is_ready_obj, py_usb_ncm_is_ready);

/* ---- module table ---- */
static const mp_rom_map_elem_t usb_ncm_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_usb_ncm) },
    { MP_ROM_QSTR(MP_QSTR_init),     MP_ROM_PTR(&py_usb_ncm_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_poll),     MP_ROM_PTR(&py_usb_ncm_poll_obj) },
    { MP_ROM_QSTR(MP_QSTR_is_ready), MP_ROM_PTR(&py_usb_ncm_is_ready_obj) },
};
static MP_DEFINE_CONST_DICT(usb_ncm_module_globals, usb_ncm_module_globals_table);

const mp_obj_module_t usb_ncm_module = {
    .base    = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&usb_ncm_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_usb_ncm, usb_ncm_module);

#endif /* CFG_TUD_NCM */
