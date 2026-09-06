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

  field(entryId) {
    return this.hass.callWS({ type: "hosekeeper/field", entry_id: entryId });
  }

  /** Confirm a job. Returns the lawn's fresh snapshot, so the caller redraws from truth. */
  log(entryId, payload) {
    return this.hass.callWS({ type: "hosekeeper/log", entry_id: entryId, ...payload });
  }
}
