(() => {
  "use strict";
  window.PanelForgeH3LoraInfo = {
    async open(name) {
      const request = window.PanelForgeLabCore.request;
      const base = "/api/h3-render/video-loras/resources";
      const resource = await request(`${base}?name=${encodeURIComponent(name)}`);
      const update = (item, values) => request(`${base}/${encodeURIComponent(item.resource_id)}/preference`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(values),
      });
      const refresh = item => request(`${base}/${encodeURIComponent(item.resource_id)}/refresh`, {method: "POST"});
      window.PanelForgeKrea2ResourceUi.openResourceInfo(resource, update, refresh);
    },
  };
})();
