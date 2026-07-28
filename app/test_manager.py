"""
Vérifie le gestionnaire multi-caméras : 3 caméras indépendantes, contrôle
global (tout démarrer / tout arrêter), indépendance réelle (une caméra
déconnectée n'empêche pas les autres), et instantané pour l'UI.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

import asyncio

from osmo_controller.manager import CameraManager
from osmo_controller.sim_transport import SimulatedTransport
from osmo_controller.simulator import OsmoCameraSimulator

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


async def wait_until(pred, timeout=3.0, interval=0.02):
    async def _loop():
        while not pred():
            await asyncio.sleep(interval)
    await asyncio.wait_for(_loop(), timeout)


def build_manager(n=3):
    mgr = CameraManager(reconnect_delay=0.05)
    cams = {}
    for i in range(1, n + 1):
        cam = OsmoCameraSimulator(battery_pct=90 - i * 5, remain_capacity_mb=40_000)
        cams[f"Terrain {i}"] = cam
        mgr.add_camera(f"Terrain {i}", SimulatedTransport(cam, tick_interval=0.05))
    return mgr, cams


async def main():
    print("1) 3 caméras se connectent indépendamment")
    mgr, cams = build_manager(3)
    mgr.start_all()
    await asyncio.gather(*(c.wait_connected(3.0) for c in mgr.cameras))
    check("les 3 sont connectées", all(c.is_connected for c in mgr.cameras))

    print("\n2) Contrôle global : tout enregistrer")
    await wait_until(lambda: all(c.last_status for c in mgr.cameras))
    res = await mgr.start_recording_all()
    check("start_recording_all : 3 succès", sum(res.values()) == 3)
    await wait_until(lambda: all(cam.is_recording for cam in cams.values()))
    check("les 3 caméras enregistrent", all(cam.is_recording for cam in cams.values()))

    print("\n3) Contrôle global : tout arrêter")
    await mgr.stop_recording_all()
    await wait_until(lambda: all(not cam.is_recording for cam in cams.values()))
    check("les 3 caméras sont arrêtées", all(not cam.is_recording for cam in cams.values()))

    print("\n4) Indépendance : contrôle par caméra")
    await mgr.get("Terrain 1").start_recording()
    await wait_until(lambda: cams["Terrain 1"].is_recording)
    check("Terrain 1 enregistre", cams["Terrain 1"].is_recording)
    check("Terrain 2 n'enregistre PAS", not cams["Terrain 2"].is_recording)
    check("Terrain 3 n'enregistre PAS", not cams["Terrain 3"].is_recording)

    print("\n5) Instantané (snapshot) pour l'UI")
    snap = mgr.snapshot()
    check("snapshot couvre les 3 caméras", len(snap) == 3)
    t1 = next(s for s in snap if s["name"] == "Terrain 1")
    check("Terrain 1 : connecté", t1["connected"] is True)
    check("Terrain 1 : en enregistrement", t1["is_recording"] is True)
    check("Terrain 1 : batterie présente", isinstance(t1["battery_pct"], int))
    print("    snapshot Terrain 1 :", t1)

    print("\n6) Robustesse : une caméra qui tombe n'affecte pas les autres")
    mgr.get("Terrain 2")._transport.simulate_drop()
    await wait_until(lambda: not mgr.get("Terrain 2").is_connected, timeout=2.0)
    check("Terrain 2 a perdu le lien", not mgr.get("Terrain 2").is_connected)
    check("Terrain 1 & 3 restent connectés",
          mgr.get("Terrain 1").is_connected and mgr.get("Terrain 3").is_connected)
    # Terrain 2 doit se reconnecter tout seul
    await mgr.get("Terrain 2").wait_connected(timeout=3.0)
    check("Terrain 2 s'est reconnecté automatiquement", mgr.get("Terrain 2").is_connected)

    await mgr.stop_all()
    check("stop_all : toutes fermées",
          all(c.state.value == "closed" for c in mgr.cameras))

    print("\n" + ("=" * 48))
    print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
    print("=" * 48)


asyncio.run(main())
sys.exit(0 if ok else 1)
