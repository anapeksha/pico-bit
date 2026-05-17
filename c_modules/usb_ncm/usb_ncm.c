#include "tusb_option.h"
#if CFG_TUD_NCM

/*
 * usb_ncm — MicroPython C module for USB CDC-NCM Ethernet.
 *
 * Bridges TinyUSB CDC-NCM frames to lwIP as a second netif alongside the
 * CYW43 Wi-Fi AP. The NCM interfaces themselves are described by MicroPython's
 * static configuration descriptor (patched at build time — see
 * scripts/release.py:_patch_micropython_for_ncm), so machine.USBDevice keeps
 * working for runtime HID on top of HID + MSC + NCM. We only own:
 *
 *   - the global MAC address symbol TinyUSB's NCM driver expects
 *   - the network RX/TX callbacks that bridge frames into lwIP
 *   - the lwIP netif registration + DHCP server bring-up
 *
 * Python API:
 *   usb_ncm.init(ip, netmask, gateway)  — register netif, start DHCP server
 *   usb_ncm.poll()                      — drive tud_task() + complete NCM init
 *   usb_ncm.is_ready()                  — True once the host has opened NCM
 */

#include <stdlib.h>
#include <string.h>

#include "py/runtime.h"
#include "py/obj.h"

#include "tusb.h"
#include "lwip/netif.h"
#include "lwip/etharp.h"
#include "lwip/pbuf.h"
#include "lwip/ip_addr.h"
#include "lwip/tcpip.h"
#include "netif/ethernet.h"
#include "shared/netutils/dhcpserver.h"  /* MicroPython DHCP server (same one CYW43 AP uses) */

/* TinyUSB's NCM driver references this symbol externally.  Lower 6 bytes of
   the RP2350 board UID, locally-administered bit set, multicast bit cleared.
   Filled by _derive_mac() before netif_add. */
uint8_t tud_network_mac_address[6] = {0x02, 0x00, 0x00, 0x00, 0x00, 0x01};

static struct netif _ncm_netif;
static dhcp_server_t _ncm_dhcp_server;
static bool _ncm_ready = false;
static volatile bool _ncm_init_pending = false;

static void _derive_mac(void) {
    extern void mp_usbd_port_get_serial_number(char *buf);
    char serial[20] = {0};
    mp_usbd_port_get_serial_number(serial);
    const char *s = serial + (strlen(serial) > 12 ? strlen(serial) - 12 : 0);
    for (int i = 0; i < 6; i++) {
        char byte_str[3] = {s[i * 2], s[i * 2 + 1], 0};
        tud_network_mac_address[i] = (uint8_t)strtol(byte_str, NULL, 16);
    }
    tud_network_mac_address[0] = (tud_network_mac_address[0] & 0xFE) | 0x02;
}

/* ---- lwIP netif callbacks ---- */
static err_t _ncm_netif_linkoutput(struct netif *netif, struct pbuf *p) {
    (void)netif;
    if (!tud_ready()) return ERR_IF;
    /* tud_network_xmit queues the pbuf; tud_network_xmit_cb copies on demand. */
    while (!tud_network_can_xmit(p->tot_len)) {
        tud_task();
    }
    tud_network_xmit(p, 0);
    return ERR_OK;
}

static err_t _ncm_netif_init(struct netif *netif) {
    netif->name[0] = 'u';
    netif->name[1] = '0';
    netif->output     = etharp_output;
    netif->linkoutput = _ncm_netif_linkoutput;
    netif->mtu        = 1500;
    netif->hwaddr_len = 6;
    memcpy(netif->hwaddr, tud_network_mac_address, 6);
    netif->flags = NETIF_FLAG_BROADCAST | NETIF_FLAG_ETHARP | NETIF_FLAG_LINK_UP;
    return ERR_OK;
}

/* ---- TinyUSB NCM callbacks (called from USB IRQ) ---- */

void tud_network_init_cb(void) {
    _ncm_init_pending = true;
}

bool tud_network_recv_cb(const uint8_t *src, uint16_t size) {
    /* MicroPython's lwIP runs with NO_SYS=0 on a separate tcpip thread.
       tcpip_input() is the only ISR-safe way to inject frames — it queues
       the pbuf via the tcpip mailbox instead of running lwIP code here. */
    struct pbuf *p = pbuf_alloc(PBUF_RAW, size, PBUF_POOL);
    if (p) {
        pbuf_take(p, src, size);
        if (tcpip_input(p, &_ncm_netif) != ERR_OK) {
            pbuf_free(p);
        }
    }
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

    /* dhcp_server_init expects ip_addr_t* (union with type tag when LWIP_IPV6=1,
       which the rp2 port enables). ip_2_ip4() narrows to ip4_addr_t* for netif_add. */
    ip_addr_t ip, netmask, gateway;
    if (!ipaddr_aton(ip_str, &ip) ||
        !ipaddr_aton(nm_str, &netmask) ||
        !ipaddr_aton(gw_str, &gateway)) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid IP address"));
    }

    _derive_mac();

    netif_add(&_ncm_netif, ip_2_ip4(&ip), ip_2_ip4(&netmask), ip_2_ip4(&gateway),
              NULL, _ncm_netif_init, tcpip_input);
    netif_set_up(&_ncm_netif);

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
