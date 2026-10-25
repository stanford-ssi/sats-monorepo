const elements = {
  runName: document.querySelector("#run-name"),
  channelCount: document.querySelector("#channel-count"),
  search: document.querySelector("#channel-search"),
  tree: document.querySelector("#source-tree"),
  panels: document.querySelector("#panels"),
  file: document.querySelector("#file-input"),
  themeToggle: document.querySelector("#theme-toggle"),
  toast: document.querySelector("#toast"),
  sidebarResizer: document.querySelector("#sidebar-resizer"),
};

let dataset;
let channels = new Map();
let selections = new Map();
let panels = [];
let nextPanelId = 1;
let selectedPanelId;

const plotConfig = { responsive: true, displaylogo: false, scrollZoom: true };
const CHANNEL_DRAG_TYPE = "application/x-ssift-channel";
const THEME_KEY = "ssift-theme";
const SIDEBAR_WIDTH_KEY = "ssift-sidebar-width";
const DEFAULT_SIDEBAR_WIDTH = 300;
const MIN_SIDEBAR_WIDTH = 220;
const MAX_SIDEBAR_WIDTH = 560;
const TRACE_COLORS = ["#4da3ff", "#ff5c5c", "#c49b00", "#21a366", "#9b61e8", "#e87918"];
let sidebarWidth = DEFAULT_SIDEBAR_WIDTH;
let plotResizeFrame;

function plotLayout() {
  const styles = getComputedStyle(document.documentElement);
  const color = (name) => styles.getPropertyValue(name).trim();
  return {
    autosize: true,
    colorway: TRACE_COLORS,
    margin: { l: 68, r: 18, t: 22, b: 56 },
    paper_bgcolor: color("--surface"),
    plot_bgcolor: color("--surface"),
    font: { color: color("--muted"), size: 12 },
    hoverlabel: {
      bgcolor: color("--raised"),
      bordercolor: color("--line-strong"),
      font: { color: color("--text") },
    },
    legend: { orientation: "h", y: 1.1 },
    xaxis: { gridcolor: color("--line"), zerolinecolor: color("--line-strong") },
    yaxis: { gridcolor: color("--line"), zerolinecolor: color("--line-strong") },
  };
}

function setTheme(theme, persist = true) {
  document.documentElement.classList.remove("theme-dark", "theme-light");
  document.documentElement.classList.add(`theme-${theme}`);
  document.documentElement.dataset.theme = theme;
  const nextTheme = theme === "dark" ? "light" : "dark";
  elements.themeToggle.textContent = nextTheme[0].toUpperCase() + nextTheme.slice(1);
  elements.themeToggle.ariaLabel = `Switch to ${nextTheme} mode`;
  if (persist) localStorage.setItem(THEME_KEY, theme);
  if (dataset) renderPanels();
}

function sidebarWidthLimits() {
  return {
    min: MIN_SIDEBAR_WIDTH,
    max: Math.max(
      MIN_SIDEBAR_WIDTH,
      Math.min(MAX_SIDEBAR_WIDTH, window.innerWidth - 360),
    ),
  };
}

function resizePlots() {
  cancelAnimationFrame(plotResizeFrame);
  plotResizeFrame = requestAnimationFrame(() => {
    document.querySelectorAll(".plot.js-plotly-plot").forEach((plot) => {
      window.Plotly?.Plots?.resize(plot);
    });
  });
}

function setSidebarWidth(width, persist = false) {
  const { min, max } = sidebarWidthLimits();
  sidebarWidth = Math.round(Math.min(max, Math.max(min, width)));
  document.documentElement.style.setProperty("--sidebar-width", `${sidebarWidth}px`);
  elements.sidebarResizer.ariaValueMin = String(min);
  elements.sidebarResizer.ariaValueMax = String(max);
  elements.sidebarResizer.ariaValueNow = String(sidebarWidth);
  elements.sidebarResizer.ariaValueText = `${sidebarWidth} pixels`;
  if (persist) localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth));
  resizePlots();
}

function enableSidebarResizing() {
  const resizer = elements.sidebarResizer;
  let startX = 0;
  let startWidth = sidebarWidth;

  function stopResizing(event) {
    if (resizer.hasPointerCapture(event.pointerId)) {
      resizer.releasePointerCapture(event.pointerId);
    }
    resizer.classList.remove("active");
    document.body.classList.remove("sidebar-resizing");
    setSidebarWidth(sidebarWidth, true);
  }

  resizer.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || window.matchMedia("(max-width: 760px)").matches) return;
    event.preventDefault();
    startX = event.clientX;
    startWidth = sidebarWidth;
    resizer.setPointerCapture(event.pointerId);
    resizer.classList.add("active");
    document.body.classList.add("sidebar-resizing");
  });
  resizer.addEventListener("pointermove", (event) => {
    if (!resizer.hasPointerCapture(event.pointerId)) return;
    setSidebarWidth(startWidth + event.clientX - startX);
  });
  resizer.addEventListener("pointerup", stopResizing);
  resizer.addEventListener("pointercancel", stopResizing);
  resizer.addEventListener("dblclick", () => setSidebarWidth(DEFAULT_SIDEBAR_WIDTH, true));
  resizer.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 48 : 16;
    const { min, max } = sidebarWidthLimits();
    const nextWidth = {
      ArrowLeft: sidebarWidth - step,
      ArrowRight: sidebarWidth + step,
      Home: min,
      End: max,
    }[event.key];
    if (nextWidth === undefined) return;
    event.preventDefault();
    setSidebarWidth(nextWidth, true);
  });
}

function channelLabel(channel) {
  const metadata = [channel.unit, channel.frame].filter(Boolean).join(" · ");
  return metadata ? `${channel.path} [${metadata}]` : channel.path;
}

function traceLabel(channel) {
  const series = channel.series ? ` · ${channel.series}` : "";
  return `${channelLabel(channel)}${series}`;
}

function shortChannelLabel(channel) {
  return channel.path.split("/").slice(-2).join("/");
}

function selectedPaths(panel) {
  return panel.type === "time"
    ? panel.channels
    : [panel.x, panel.y].filter(Boolean);
}

function axisLabel(axis) {
  return axis.unit ? `${axis.label} (${axis.unit})` : axis.label;
}

function storageKey() {
  return `ssift-layout:v1:${dataset.name}`;
}

function saveLayout() {
  localStorage.setItem(storageKey(), JSON.stringify(panels));
}

function loadLayout() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey()));
    panels = Array.isArray(saved) ? saved : [];
  } catch {
    panels = [];
  }
  panels = panels
    .filter((panel) => ["time", "scatter"].includes(panel.type))
    .map((panel) => ({
      ...panel,
      channels: (panel.channels || []).filter((path) => selections.has(path)),
      x: selections.has(panel.x) ? panel.x : null,
      y: selections.has(panel.y) ? panel.y : null,
    }));
  if (!panels.length) addPanel("time", false);
  nextPanelId = Math.max(...panels.map((panel) => panel.id), 0) + 1;
  selectedPanelId = panels[0].id;
}

function addPanel(type, persist = true) {
  const panel = { id: nextPanelId++, type, channels: [], x: null, y: null };
  panels.push(panel);
  selectedPanelId = panel.id;
  if (persist) {
    saveLayout();
    refreshChannelButtons();
    renderPanels();
  }
}

function removePanel(id) {
  panels = panels.filter((panel) => panel.id !== id);
  if (!panels.length) addPanel("time", false);
  if (selectedPanelId === id) selectedPanelId = panels[0].id;
  saveLayout();
  refreshChannelButtons();
  renderPanels();
}

function buildTree(filter = "") {
  const root = {};
  for (const channel of selections.values()) {
    if (!channel.path.toLowerCase().includes(filter.toLowerCase())) continue;
    let node = root;
    for (const part of channel.path.split("/")) {
      node[part] ??= {};
      node = node[part];
    }
    node.__channel = channel;
  }
  elements.tree.replaceChildren(renderTreeNode(root, 0));
}

function renderTreeNode(node, depth) {
  const fragment = document.createDocumentFragment();
  for (const [name, child] of Object.entries(node).filter(([key]) => key !== "__channel")) {
    if (child.__channel) {
      fragment.append(channelButton(child.__channel));
      continue;
    }
    const details = document.createElement("details");
    details.open = depth < 2;
    const summary = document.createElement("summary");
    summary.textContent = name;
    details.append(summary, renderTreeNode(child, depth + 1));
    fragment.append(details);
  }
  return fragment;
}

function channelButton(channel) {
  const button = document.createElement("button");
  button.className = "channel";
  const selected = selectedPaths(
    panels.find((panel) => panel.id === selectedPanelId) || { type: "time", channels: [] },
  ).includes(channel.path);
  button.classList.toggle("active", selected);
  button.ariaPressed = String(selected);
  button.dataset.path = channel.path;
  button.draggable = true;
  button.title = channel.path;
  button.innerHTML = `<span class="channel-name"></span><span class="channel-meta"></span>`;
  button.querySelector(".channel-name").textContent = channel.path.split("/").at(-1);
  button.querySelector(".channel-meta").textContent =
    [
      channel.unit || "unitless",
      channel.frame,
      channel.members.length > 1 ? `${channel.members.length} series` : null,
    ].filter(Boolean).join(" · ");
  button.addEventListener("dragstart", (event) => {
    event.dataTransfer.setData(CHANNEL_DRAG_TYPE, channel.path);
  });
  button.addEventListener("click", () => toggleChannelInSelectedPanel(channel.path));
  return button;
}

function refreshChannelButtons() {
  const panel = panels.find((candidate) => candidate.id === selectedPanelId);
  const selected = new Set(panel ? selectedPaths(panel) : []);
  elements.tree.querySelectorAll(".channel").forEach((button) => {
    const active = selected.has(button.dataset.path);
    button.classList.toggle("active", active);
    button.ariaPressed = String(active);
  });
}

function toggleChannelInSelectedPanel(path) {
  const panel = panels.find((candidate) => candidate.id === selectedPanelId);
  if (!panel) return;
  if (panel.type === "time") {
    panel.channels = panel.channels.includes(path)
      ? panel.channels.filter((candidate) => candidate !== path)
      : [...panel.channels, path];
  } else if (panel.x === path) {
    panel.x = null;
  } else if (panel.y === path) {
    panel.y = null;
  } else if (!panel.x) {
    panel.x = path;
  } else {
    panel.y = path;
  }
  saveLayout();
  refreshChannelButtons();
  renderPanels();
}

function selectPanel(id) {
  if (selectedPanelId === id) return;
  selectedPanelId = id;
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("selected", Number(panel.dataset.panelId) === id);
  });
  refreshChannelButtons();
}

function dropPath(event) {
  event.preventDefault();
  return event.dataTransfer.getData(CHANNEL_DRAG_TYPE);
}

function acceptDrop(element, handler) {
  element.addEventListener("dragover", (event) => {
    if (!event.dataTransfer.types.includes(CHANNEL_DRAG_TYPE)) return;
    event.preventDefault();
    element.closest(".panel")?.classList.add("drag-over");
  });
  element.addEventListener("dragleave", (event) => {
    if (!event.dataTransfer.types.includes(CHANNEL_DRAG_TYPE)) return;
    element.closest(".panel")?.classList.remove("drag-over");
  });
  element.addEventListener("drop", (event) => {
    if (!event.dataTransfer.types.includes(CHANNEL_DRAG_TYPE)) return;
    element.closest(".panel")?.classList.remove("drag-over");
    const path = dropPath(event);
    if (selections.has(path)) handler(path);
  });
}

function clearReorderIndicators() {
  document.querySelectorAll(".reorder-before, .reorder-after").forEach((element) => {
    element.classList.remove("reorder-before", "reorder-after");
  });
}

function panelColumns(count) {
  if (window.matchMedia("(max-width: 760px)").matches) return 1;
  if (count <= 3) return count;
  if (count === 4) return 2;
  if (count <= 6) return 3;
  if (count <= 8) return 4;
  return Math.ceil(Math.sqrt(count));
}

function fitPanels() {
  const columns = panelColumns(panels.length);
  const rows = Math.ceil(panels.length / columns);
  elements.panels.style.setProperty(
    "--panel-width",
    `calc((100% - ${(columns - 1) * 8}px) / ${columns})`,
  );
  elements.panels.style.setProperty(
    "--panel-height",
    `calc((100% - ${(rows - 1) * 8}px) / ${rows})`,
  );
}

function reorderPanel(draggedId, targetId, after) {
  if (draggedId === targetId) return;
  const draggedIndex = panels.findIndex((panel) => panel.id === draggedId);
  if (draggedIndex < 0) return;
  const [dragged] = panels.splice(draggedIndex, 1);
  const targetIndex = panels.findIndex((panel) => panel.id === targetId);
  panels.splice(targetIndex + Number(after), 0, dragged);
  saveLayout();
  renderPanels();
}

function reorderTarget(clientX, clientY) {
  const article = document.elementFromPoint(clientX, clientY)?.closest(".panel");
  if (!article) return null;
  const bounds = article.getBoundingClientRect();
  return {
    article,
    id: Number(article.dataset.panelId),
    after: clientY > bounds.top + bounds.height / 2,
  };
}

function enablePanelReordering(article, panel) {
  const handle = article.querySelector(".drag-handle");
  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    article.classList.add("dragging");
  });
  handle.addEventListener("pointermove", (event) => {
    if (!handle.hasPointerCapture(event.pointerId)) return;
    clearReorderIndicators();
    const target = reorderTarget(event.clientX, event.clientY);
    target?.article.classList.add(target.after ? "reorder-after" : "reorder-before");
  });
  handle.addEventListener("pointerup", (event) => {
    if (!handle.hasPointerCapture(event.pointerId)) return;
    const target = reorderTarget(event.clientX, event.clientY);
    handle.releasePointerCapture(event.pointerId);
    article.classList.remove("dragging");
    clearReorderIndicators();
    if (target) reorderPanel(panel.id, target.id, target.after);
  });
  handle.addEventListener("pointercancel", () => {
    article.classList.remove("dragging");
    clearReorderIndicators();
  });
}

function renderPanels() {
  elements.panels.replaceChildren();
  fitPanels();
  for (const panel of panels) elements.panels.append(renderPanel(panel));
}

function renderPanel(panel) {
  const article = document.createElement("article");
  article.className = panel.id === selectedPanelId ? "panel selected" : "panel";
  article.dataset.panelId = panel.id;
  article.addEventListener("pointerdown", () => selectPanel(panel.id));
  article.innerHTML = `
    <header class="panel-header">
      <div class="panel-heading">
        <span class="drag-handle" title="Drag to reorder">⠿</span>
        <span class="panel-kind"></span>
        <span class="panel-title"></span>
        <span class="panel-selection-count"></span>
      </div>
      <button class="remove-panel" type="button" aria-label="Remove panel">✕</button>
    </header>
    <div class="axis-targets"></div>
    <div class="plot"></div>
    <div class="channel-chips"></div>`;
  article.querySelector(".panel-kind").textContent = panel.type === "time" ? "Time" : "XY";
  article.querySelector(".panel-title").textContent =
    panel.type === "time" ? "Time series" : "Scatter";
  const selectionCount = selectedPaths(panel).length;
  article.querySelector(".panel-selection-count").textContent =
    `${selectionCount} ${selectionCount === 1 ? "channel" : "channels"}`;
  article.querySelector(".remove-panel").addEventListener("click", () => removePanel(panel.id));
  enablePanelReordering(article, panel);

  if (panel.type === "time") {
    acceptDrop(article, (path) => {
      if (!panel.channels.includes(path)) panel.channels.push(path);
      saveLayout();
      refreshChannelButtons();
      renderPanels();
    });
    requestAnimationFrame(() => renderTimePlot(article, panel));
  } else {
    requestAnimationFrame(() => renderScatterPlot(article, panel));
  }
  return article;
}

function renderTimePlot(article, panel) {
  const plot = article.querySelector(".plot");
  const selected = panel.channels.map((path) => selections.get(path)).filter(Boolean);
  renderChips(article, panel, selected);
  if (!selected.length) return showEmpty(plot, "Drop one or more channels here");

  const traces = selected.flatMap((selection, index) =>
    selection.members.map((channel, seriesIndex) => ({
      x: dataset.axes[channel.axis].values,
      y: channel.values,
      type: "scattergl",
      mode: "lines",
      name: channel.series
        ? `${shortChannelLabel(selection)} · ${channel.series}`
        : shortChannelLabel(selection),
      legendgroup: selection.path,
      line: {
        color: TRACE_COLORS[
          (selection.members.length > 1 ? seriesIndex : index) % TRACE_COLORS.length
        ],
      },
      opacity: selection.members.length > 1 ? 0.8 : 1,
      meta: traceLabel(channel),
      hovertemplate: "%{meta}<br>%{y}<extra></extra>",
    })),
  );
  const units = [...new Set(selected.map((channel) => channel.unit || "unitless"))];
  const axisLabels = [
    ...new Set(
      selected.flatMap((selection) =>
        selection.members.map((channel) => axisLabel(dataset.axes[channel.axis])),
      ),
    ),
  ];
  const layout = plotLayout();
  Plotly.react(
    plot,
    traces,
    {
      ...layout,
      uirevision: panel.id,
      width: plot.clientWidth,
      xaxis: { ...layout.xaxis, title: axisLabels.join(" · ") },
      yaxis: { ...layout.yaxis, title: units.join(" · ") },
    },
    plotConfig,
  );
}

function renderScatterPlot(article, panel) {
  const targets = article.querySelector(".axis-targets");
  for (const axis of ["x", "y"]) {
    const target = document.createElement("div");
    target.className = "axis-target";
    target.innerHTML = `<strong>${axis.toUpperCase()}</strong><span></span>`;
    target.querySelector("span").textContent = panel[axis]
      ? channelLabel(selections.get(panel[axis]))
      : `Drop ${axis.toUpperCase()} channel`;
    acceptDrop(target, (path) => {
      panel[axis] = path;
      saveLayout();
      refreshChannelButtons();
      renderPanels();
    });
    targets.append(target);
  }

  const plot = article.querySelector(".plot");
  const xChannel = selections.get(panel.x);
  const yChannel = selections.get(panel.y);
  renderChips(article, panel, [xChannel, yChannel].filter(Boolean));
  if (!xChannel || !yChannel) return showEmpty(plot, "Choose X and Y channels above");
  const yBySeries = new Map(yChannel.members.map((channel) => [channel.series, channel]));
  const pairs = xChannel.members.flatMap((x) => {
    const y = xChannel.members.length === 1 && yChannel.members.length === 1
      ? yChannel.members[0]
      : yBySeries.get(x.series);
    return y ? [[x, y]] : [];
  });
  if (!pairs.length || pairs.some(([x, y]) => x.axis !== y.axis)) {
    return showEmpty(plot, "XY channels need matching series and axes");
  }
  const layout = plotLayout();
  const traces = pairs.map(([x, y], index) => {
    const sampleAxis = dataset.axes[x.axis];
    const oneSeries = pairs.length === 1;
    return {
      x: x.values,
      y: y.values,
      type: "scattergl",
      mode: "markers",
      name: x.series || shortChannelLabel(xChannel),
      marker: oneSeries
        ? { color: sampleAxis.values, colorscale: "Viridis", size: 5, colorbar: { title: axisLabel(sampleAxis) } }
        : { color: TRACE_COLORS[index % TRACE_COLORS.length], size: 5 },
      meta: x.series || "",
      hovertemplate: oneSeries
        ? `x=%{x}<br>y=%{y}<br>${sampleAxis.label}=%{marker.color}<extra></extra>`
        : "%{meta}<br>x=%{x}<br>y=%{y}<extra></extra>",
    };
  });
  Plotly.react(
    plot,
    traces,
    {
      ...layout,
      showlegend: pairs.length > 1,
      uirevision: panel.id,
      width: plot.clientWidth,
      xaxis: { ...layout.xaxis, title: channelLabel(xChannel) },
      yaxis: { ...layout.yaxis, title: channelLabel(yChannel) },
    },
    plotConfig,
  );
}

function renderChips(article, panel, selected) {
  const container = article.querySelector(".channel-chips");
  if (!selected.length) return;
  const label = document.createElement("span");
  label.className = "selected-label";
  label.textContent = "Selected";
  container.append(label);
  for (const [index, channel] of selected.entries()) {
    const path = channel.path;
    const chip = document.createElement("span");
    chip.className = "channel-chip";
    chip.title = channelLabel(channel);
    const marker = document.createElement("span");
    if (panel.type === "time") {
      marker.className = "channel-swatch";
      marker.style.background = channel.members.length > 1
        ? `linear-gradient(90deg, ${TRACE_COLORS.join(", ")})`
        : TRACE_COLORS[index % TRACE_COLORS.length];
    } else {
      marker.className = "channel-role";
      marker.textContent = panel.x === path ? "X" : "Y";
    }
    const name = document.createElement("span");
    name.className = "channel-chip-label";
    name.textContent = shortChannelLabel(channel);
    if (channel.members.length > 1) name.textContent += ` · ${channel.members.length} series`;
    const remove = document.createElement("button");
    remove.className = "remove-channel";
    remove.type = "button";
    remove.ariaLabel = `Remove ${channelLabel(channel)}`;
    remove.textContent = "×";
    chip.append(marker, name, remove);
    remove.addEventListener("click", () => {
      panel.channels = panel.channels.filter((candidate) => candidate !== path);
      if (panel.x === path) panel.x = null;
      if (panel.y === path) panel.y = null;
      saveLayout();
      refreshChannelButtons();
      renderPanels();
    });
    container.append(chip);
  }
}

function showEmpty(plot, message) {
  Plotly.purge(plot);
  plot.innerHTML = `<div class="plot-empty"></div>`;
  plot.firstElementChild.textContent = message;
}

function showError(error) {
  elements.toast.textContent = error.message || String(error);
  elements.toast.style.display = "block";
  setTimeout(() => (elements.toast.style.display = "none"), 5000);
}

function validateDataset(candidate) {
  if (candidate.schema_version !== 2 || !candidate.axes || !Array.isArray(candidate.channels)) {
    throw new Error("Unsupported telemetry file");
  }
  const paths = new Set();
  const seriesByGroup = new Map();
  for (const channel of candidate.channels) {
    const axis = candidate.axes[channel.axis];
    if (!channel.path || paths.has(channel.path) || !axis) {
      throw new Error("Telemetry channels need unique paths and valid axes");
    }
    if (!Array.isArray(channel.values) || channel.values.length !== axis.values?.length) {
      throw new Error(`Channel length does not match its axis: ${channel.path}`);
    }
    if (channel.group) {
      if (!channel.series) throw new Error(`Grouped channel needs a series: ${channel.path}`);
      const series = seriesByGroup.get(channel.group) || new Set();
      if (series.has(channel.series)) {
        throw new Error(`Duplicate series in channel group: ${channel.group}`);
      }
      series.add(channel.series);
      seriesByGroup.set(channel.group, series);
    }
    paths.add(channel.path);
  }
  if ([...paths].some((left) => [...paths].some((right) => right.startsWith(`${left}/`)))) {
    throw new Error("Telemetry channel paths cannot prefix one another");
  }
}

function buildSelections() {
  selections = new Map();
  for (const channel of channels.values()) {
    const path = channel.group || channel.path;
    if (!selections.has(path)) {
      selections.set(path, {
        path,
        unit: channel.unit,
        frame: channel.frame,
        members: [],
      });
    }
    selections.get(path).members.push(channel);
  }
}

function useDataset(nextDataset) {
  validateDataset(nextDataset);
  dataset = nextDataset;
  channels = new Map(dataset.channels.map((channel) => [channel.path, channel]));
  buildSelections();
  elements.runName.textContent = dataset.name;
  elements.channelCount.textContent = `${selections.size} channels`;
  elements.search.value = "";
  loadLayout();
  buildTree();
  renderPanels();
}

document.querySelector("#add-time-series").addEventListener("click", () => addPanel("time"));
document.querySelector("#add-scatter").addEventListener("click", () => addPanel("scatter"));
elements.themeToggle.addEventListener("click", () =>
  setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"),
);
document.querySelector("#reset-layout").addEventListener("click", () => {
  localStorage.removeItem(storageKey());
  panels = [];
  addPanel("time", false);
  refreshChannelButtons();
  renderPanels();
});
elements.search.addEventListener("input", () => buildTree(elements.search.value));
elements.file.addEventListener("change", async () => {
  try {
    useDataset(JSON.parse(await elements.file.files[0].text()));
  } catch (error) {
    showError(error);
  }
});
window.addEventListener("resize", () => {
  setSidebarWidth(sidebarWidth);
  fitPanels();
});
enableSidebarResizing();
setSidebarWidth(Number(localStorage.getItem(SIDEBAR_WIDTH_KEY)) || DEFAULT_SIDEBAR_WIDTH);
setTheme(document.documentElement.dataset.theme, false);

fetch("/telemetry.json")
  .then((response) => response.json())
  .then(useDataset)
  .catch(showError);
