/**
 * The panel's side of the websocket API.
 *
 * It reads snapshots, and it writes one thing: that a job on the screen was done. That write
 * lives here rather than in a device page because the confirmation belongs beside the line
 * that asked for the job. The integration's services stay for automations. It can also ask
 * the engine to work every lawn out again, which changes no record, only the conclusions.
 */

export class HosekeeperApi {
  constructor(hass) {
    this.hass = hass;
  }

  fields() {
    return this.hass.callWS({ type: "hosekeeper/fields" });
  }

  field(zoneId) {
    return this.hass.callWS({ type: "hosekeeper/field", zone_id: zoneId });
  }

  /** Recalculate every lawn now, settled plans included. Resolves once it is done. */
  recompute() {
    return this.hass.callWS({ type: "hosekeeper/recompute" });
  }

  /** Confirm a job. Returns the lawn's fresh snapshot, so the caller redraws from truth. */
  log(zoneId, payload) {
    return this.hass.callWS({ type: "hosekeeper/log", zone_id: zoneId, ...payload });
  }
}
