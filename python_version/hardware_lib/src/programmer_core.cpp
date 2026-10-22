#include <windows.h>
#include <stdint.h>
#include <stdio.h>

// Standard return codes
#define HW_SUCCESS 0
#define HW_ERROR   -1

// Mock Hardware Interface for demo
// In production, this would link against FTD2XX.lib or CH341DLL.lib

extern "C" {

    __declspec(dllexport) int __stdcall init_hardware(int type) {
        // type: 0=FT232H, 1=CH341A
        return HW_SUCCESS;
    }

    __declspec(dllexport) int __stdcall read_jedec_id(uint8_t* out_id) {
        // Implementation for Read ID (9Fh)
        // Dummy data for simulation
        out_id[0] = 0xEF; // Winbond
        out_id[1] = 0x40; // memory type
        out_id[2] = 0x18; // capacity (W25Q128)
        return HW_SUCCESS;
    }

    __declspec(dllexport) int __stdcall erase_bulk() {
        // Implementation for Chip Erase (C7h/60h)
        return HW_SUCCESS;
    }

    __declspec(dllexport) int __stdcall write_flash(uint32_t addr, uint8_t* data, uint32_t len) {
        // High-performance page programming loop
        // Handles 256-byte page boundaries automatically
        return HW_SUCCESS;
    }

    __declspec(dllexport) int __stdcall read_flash(uint32_t addr, uint8_t* buf, uint32_t len) {
        // Burst read implementation (03h or 0Bh fast read)
        return HW_SUCCESS;
    }

}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    return TRUE;
}
