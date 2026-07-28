"""
Vérifie la machine à états de connexion (la couche « erreur proof ») contre
le simulateur, en simulant de vraies pannes : échecs de connexion initiaux
et coupure du lien en plein vol. Tout tourne sans matériel.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")  # console Windows : autoriser ✔ et accents

import asyncio

from osmo_controller.connection import (
    CameraConnection, ConnectionState, NotConnectedError,
)
from osmo_controller.sim_transport import SimulatedTransport
from osmo_controller.simulator import OsmoCameraSimulator

ok = True


def check(label, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FAIL'}] {label}")
    ok = ok and cond


async def wait_until(pred, timeout=3.0, interval=0.02):
    """Attend que pred() soit vrai, sinon lève TimeoutError."""
    async def _loop():
        while not pred():
            await asyncio.sleep(interval)
    await asyncio.wait_for(_loop(), timeout)


async def test_connect_and_status():
    print("1) Connexion : passe CONNECTED, s'abonne, reçoit le statut")
    statuses = []
    states = []
    cam = OsmoCameraSimulator(battery_pct=77, remain_capacity_mb=50_000)
    tr = SimulatedTransport(cam, tick_interval=0.05)
    conn = CameraConnection(tr, name="cam1", reconnect_delay=0.05,
                            on_status=statuses.append, on_state=states.append)
    conn.start()
    await conn.wait_connected(timeout=3.0)
    check("état == CONNECTED", conn.state is ConnectionState.CONNECTED)
    await wait_until(lambda: len(statuses) >= 1)
    check("au moins un push de statut reçu", len(statuses) >= 1)
    check("dernier statut : batterie == 77 %", conn.last_status["battery_pct"] == 77)
    await conn.stop()
    check("état == CLOSED après stop", conn.state is ConnectionState.CLOSED)


async def test_recording():
    print("\n2) Enregistrement à distance : START puis STOP via la connexion")
    cam = OsmoCameraSimulator()
    tr = SimulatedTransport(cam, tick_interval=0.05)
    conn = CameraConnection(tr, name="cam2", reconnect_delay=0.05)
    conn.start()
    await conn.wait_connected(3.0)
    await conn.start_recording()
    await wait_until(lambda: conn.last_status and conn.last_status["is_recording"])
    check("la caméra enregistre après start_recording()", cam.is_recording is True)
    await conn.stop_recording()
    await wait_until(lambda: conn.last_status and not conn.last_status["is_recording"])
    check("la caméra s'arrête après stop_recording()", cam.is_recording is False)
    await conn.stop()


async def test_command_when_disconnected():
    print("\n3) Sécurité : une commande hors connexion lève NotConnectedError")
    tr = SimulatedTransport(tick_interval=0.05)
    conn = CameraConnection(tr, name="cam3")
    raised = False
    try:
        await conn.start_recording()       # jamais connecté
    except NotConnectedError:
        raised = True
    check("NotConnectedError levée", raised)


async def test_retry_on_initial_failure():
    print("\n4) Retry : 2 échecs de connexion puis succès automatique")
    tr = SimulatedTransport(tick_interval=0.05, fail_times=2)
    states = []
    conn = CameraConnection(tr, name="cam4", reconnect_delay=0.05,
                            on_state=states.append)
    conn.start()
    await conn.wait_connected(timeout=3.0)
    check("finit par se connecter malgré les échecs", conn.is_connected)
    check("est passé par RECONNECTING", ConnectionState.RECONNECTING in states)
    await conn.stop()


async def test_auto_reconnect_on_drop():
    print("\n5) Reconnexion auto : coupure en plein vol → revient CONNECTED")
    tr = SimulatedTransport(tick_interval=0.05)
    states = []
    conn = CameraConnection(tr, name="cam5", reconnect_delay=0.05,
                            on_state=states.append)
    conn.start()
    await conn.wait_connected(3.0)
    check("connecté une 1re fois", conn.is_connected)

    tr.simulate_drop()                      # le BLE tombe
    await wait_until(lambda: conn.state is not ConnectionState.CONNECTED, timeout=2.0)
    check("a détecté la perte de lien", conn.state is not ConnectionState.CONNECTED)

    await conn.wait_connected(timeout=3.0)  # doit se reconnecter tout seul
    check("s'est reconnecté automatiquement", conn.is_connected)
    check("a bien transité par RECONNECTING", ConnectionState.RECONNECTING in states)

    # Et le statut recommence à arriver après reconnexion.
    n = len(states)
    last = conn.last_status
    await wait_until(lambda: conn.last_status is not None, timeout=2.0)
    check("le statut repart après reconnexion", conn.last_status is not None)
    await conn.stop()


async def test_no_reconnect_after_stop():
    print("\n6) stop() est définitif : pas de reconnexion après une coupure")
    tr = SimulatedTransport(tick_interval=0.05)
    conn = CameraConnection(tr, name="cam6", reconnect_delay=0.05)
    conn.start()
    await conn.wait_connected(3.0)
    await conn.stop()
    check("état == CLOSED", conn.state is ConnectionState.CLOSED)
    tr.simulate_drop()                      # ne doit rien relancer
    await asyncio.sleep(0.2)
    check("toujours CLOSED, aucune reconnexion", conn.state is ConnectionState.CLOSED)


async def main():
    await test_connect_and_status()
    await test_recording()
    await test_command_when_disconnected()
    await test_retry_on_initial_failure()
    await test_auto_reconnect_on_drop()
    await test_no_reconnect_after_stop()

    print("\n" + ("=" * 48))
    print("  TOUS LES TESTS PASSENT ✔" if ok else "  ÉCHEC — voir ci-dessus")
    print("=" * 48)


asyncio.run(main())
sys.exit(0 if ok else 1)
