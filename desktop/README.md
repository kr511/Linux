# desktop/

Platzhalter für die spätere Kairo-Desktopumgebung (inspiriert von Omarchy und
Hyprland).

**Absichtlich leer in Phase 1.** Ein Desktop kommt erst, wenn die Konsolen-ISO
zuverlässig bootet. Sonst debuggt man drei Baustellen gleichzeitig: Bootloader,
Kernel und Grafik-Stack.

Geplant (Phase 3, nichts davon ist umgesetzt):

- Hyprland als Wayland-Compositor (offizielles Arch-Paket `hyprland`)
- Kairo-Dotfiles als eigenes Paket unter `packages/`
- Test zuerst in QEMU mit `virtio-gpu`, dann auf der RX 6500 XT
