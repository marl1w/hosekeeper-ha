/**
 * The panel's side of the websocket API.
 *
 * It reads snapshots, and it writes one thing: that a job on the screen was done. That write
 * lives here rather than in a device page because the confirmation belongs beside the line
 * that asked for the job. The integration's services stay for automations.
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

  /** Confirm a job. Returns the lawn's fresh snapshot, so the caller redraws from truth. */
  log(zoneId, payload) {
    return this.hass.callWS({ type: "hosekeeper/log", zone_id: zoneId, ...payload });
  }
}
