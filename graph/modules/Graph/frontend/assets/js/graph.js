const NODE_RADIUS = 28;

export class TreeGraphRenderer {
  constructor({ svgSelector, emptySelector, onNodeClick }) {
    this.svg = d3.select(svgSelector);
    this.empty = document.querySelector(emptySelector);
    this.onNodeClick = onNodeClick;

    this.selectedNodeId = null;
    this.highlightNodeId = null;
    this.positions = new Map();
    this.currentTransform = d3.zoomIdentity;
    this.simulation = null;
    this.nodeById = new Map();
    this.pathNodeIds = null;
    this.pathLinkKeys = null;

    this.zoom = d3.zoom().scaleExtent([0.22, 2.8]).on('zoom', (event) => {
      this.currentTransform = event.transform;
      this.viewport.attr('transform', event.transform);
    });

    this.svg.call(this.zoom);
    this.viewport = this.svg.append('g').attr('class', 'viewport');
    this._buildMarker();
  }

  _buildMarker() {
    const defs = this.svg.select('defs').empty() ? this.svg.append('defs') : this.svg.select('defs');
    defs.select('#resolved').remove();
    const marker = defs.append('marker')
      .attr('id', 'resolved')
      .attr('markerUnits', 'userSpaceOnUse')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', NODE_RADIUS + 6)
      .attr('refY', -1)
      .attr('markerWidth', 12)
      .attr('markerHeight', 12)
      .attr('orient', 'auto')
      .attr('stroke-width', 2);
    marker.append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#B43232');
  }

  clear() {
    this._stopSimulation();
    this.viewport.selectAll('*').remove();
    this.nodeById = new Map();
    this.positions = new Map();
    if (this.empty) this.empty.style.display = 'flex';
  }

  setSelected(nodeId) {
    this.selectedNodeId = nodeId || null;
    this._applyNodeState();
    this._applyLineState();
  }

  setHighlight(nodeId) {
    this.highlightNodeId = nodeId || null;
    this._applyNodeState();
    this._applyLineState();
  }

  setPathFocus(nodeIds, linkKeys) {
    this.pathNodeIds = nodeIds instanceof Set ? nodeIds : null;
    this.pathLinkKeys = linkKeys instanceof Set ? linkKeys : null;
    this._applyNodeState();
    this._applyLineState();
  }

  clearPathFocus() {
    this.pathNodeIds = null;
    this.pathLinkKeys = null;
    this._applyNodeState();
    this._applyLineState();
  }

  render(graphData) {
    this._stopSimulation();
    this.viewport.selectAll('*').remove();

    const built = this._buildGraph(graphData || {});
    const nodes = built.nodes;
    const links = built.links;

    if (!nodes.length) {
      this.clear();
      return { positions: new Map() };
    }

    if (this.empty) this.empty.style.display = 'none';
    this.positions = new Map();

    this.linkSelection = this.viewport
      .selectAll('.edgepath')
      .data(links)
      .enter()
      .append('path')
      .attr('class', 'edgepath')
      .attr('marker-end', 'url(#resolved)');

    this.labelSelection = this.viewport
      .selectAll('.edgelabel')
      .data(links)
      .enter()
      .append('text')
      .attr('class', 'edgelabel')
      .text((d) => d.rela || '');

    const drag = d3.drag()
      .on('start', (event, d) => {
        if (!event.active && this.simulation) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active && this.simulation) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    this.nodeSelection = this.viewport
      .selectAll('.node-card')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node-card')
      .call(drag);

    this.nodeSelection
      .append('circle')
      .attr('class', 'node-circle')
      .attr('r', NODE_RADIUS)
      .on('click', (event, d) => {
        event.stopPropagation();
        this.onNodeClick?.(d);
      });

    this.nodeSelection
      .append('text')
      .attr('class', 'node-label')
      .attr('dy', '.35em')
      .attr('text-anchor', 'middle')
      .each((d, idx, nodeList) => {
        const text = d3.select(nodeList[idx]);
        this._renderLabel(text, d.name || d.id || '');
      });

    this.simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).distance(180).strength(0.35))
      .force('charge', d3.forceManyBody().strength(-1500))
      .force('center', d3.forceCenter(0, 0))
      .on('tick', () => {
        this.linkSelection.attr('d', (d) => `M ${d.source.x} ${d.source.y} L ${d.target.x} ${d.target.y}`);
        this.nodeSelection.attr('transform', (d) => `translate(${d.x},${d.y})`);
        this.labelSelection.attr('transform', (d) => {
          const x = (d.source.x + d.target.x) / 2;
          const y = (d.source.y + d.target.y) / 2;
          return `translate(${x},${y})`;
        });

        this.positions.clear();
        nodes.forEach((node) => this.positions.set(node.id, { x: node.x, y: node.y }));
      });

    this._applyNodeState();
    this._applyLineState();
    return { positions: this.positions };
  }

  resetView(animated = true) {
    const width = this._getWidth();
    const height = this._getHeight();
    const target = d3.zoomIdentity.translate(width / 2, height / 2).scale(0.88);
    const selection = animated ? this.svg.transition().duration(450) : this.svg;
    selection.call(this.zoom.transform, target);
  }

  focusNode(position, scale = 1.06) {
    if (!position) return;
    const width = this._getWidth();
    const height = this._getHeight();
    const target = d3.zoomIdentity
      .translate(width / 2 - position.x * scale, height / 2 - position.y * scale)
      .scale(scale);
    this.svg.transition().duration(500).call(this.zoom.transform, target);
  }

  _buildGraph(data) {
    const rawNodes = Array.isArray(data.nodes) ? data.nodes : [];
    const rawLinks = Array.isArray(data.links) ? data.links : [];
    const nodesMap = {};

    const links = rawLinks
      .filter((item) => item?.source && item?.target)
      .map((item, index) => {
        if (!nodesMap[item.source]) {
          nodesMap[item.source] = { id: item.source, name: item.source, attrs: {} };
        }
        if (!nodesMap[item.target]) {
          nodesMap[item.target] = { id: item.target, name: item.target, attrs: {} };
        }
        const relation = item.relation || item.label || '';
        return {
          source: nodesMap[item.source],
          target: nodesMap[item.target],
          rela: relation,
          key: `${item.source}|||${item.target}|||${relation}|||${index}`,
        };
      });

    rawNodes.forEach((item) => {
      const nodeId = item?.id;
      if (!nodeId) return;
      if (!nodesMap[nodeId]) {
        nodesMap[nodeId] = { id: nodeId, name: nodeId, attrs: {} };
      }
      nodesMap[nodeId].id = nodeId;
      nodesMap[nodeId].name = item.name || nodeId;
      nodesMap[nodeId].attrs = item.attrs || {};
      nodesMap[nodeId].attrs_blocks = Array.isArray(item.attrs_blocks) ? item.attrs_blocks : [];
      nodesMap[nodeId].type = item.type;
      nodesMap[nodeId].level = item.level;
      nodesMap[nodeId].fixed = item.fixed;
      nodesMap[nodeId].leaf = item.leaf;
      nodesMap[nodeId].summary = item.summary || '';
      nodesMap[nodeId].identity_key = item.identity_key;
      nodesMap[nodeId].parent_id = item.parent_id;
      nodesMap[nodeId].side = item.side;
      nodesMap[nodeId].tags = item.tags || [];
      nodesMap[nodeId].merged_entity = Boolean(item.merged_entity);
      nodesMap[nodeId].merged_entity_kind = item.merged_entity_kind || null;
    });

    const nodes = Object.values(nodesMap);
    this.nodeById = new Map(nodes.map((node) => [node.id, node]));
    return { nodes, links };
  }

  _renderLabel(textEl, name) {
    textEl.selectAll('tspan').remove();
    const reEn = /[a-zA-Z]+/g;
    if (name.match(reEn) || name.length <= 4) {
      textEl.append('tspan').text(name);
      return;
    }
    const top = name.substring(0, 4);
    const bottom = name.substring(4, name.length);
    textEl.append('tspan').attr('x', 0).attr('y', -7).text(top);
    textEl.append('tspan').attr('x', 0).attr('y', 10).text(bottom);
  }

  _applyNodeState() {
    if (!this.nodeSelection) return;
    const hasPathFocus = this.pathNodeIds instanceof Set && this.pathNodeIds.size > 0;
    this.nodeSelection
      .classed('selected', (d) => d.id === this.selectedNodeId)
      .classed('highlight', (d) => d.id === this.highlightNodeId)
      .classed('active-path', (d) => hasPathFocus && this.pathNodeIds.has(d.id))
      .classed('dimmed', (d) => hasPathFocus && !this.pathNodeIds.has(d.id));
  }

  _applyLineState() {
    if (!this.linkSelection) return;
    const focusIds = new Set([this.selectedNodeId, this.highlightNodeId].filter(Boolean));
    const hasPathFocus = this.pathLinkKeys instanceof Set && this.pathLinkKeys.size > 0;
    this.linkSelection
      .classed('active', (d) => focusIds.size > 0 && (d.source.id === this.selectedNodeId || d.target.id === this.selectedNodeId || d.source.id === this.highlightNodeId || d.target.id === this.highlightNodeId))
      .classed('active-path', (d) => hasPathFocus && this.pathLinkKeys.has(d.key))
      .classed('dimmed', (d) => {
        if (hasPathFocus) {
          return !this.pathLinkKeys.has(d.key);
        }
        return focusIds.size > 0 && !(d.source.id === this.selectedNodeId || d.target.id === this.selectedNodeId || d.source.id === this.highlightNodeId || d.target.id === this.highlightNodeId);
      });
    if (this.labelSelection) {
      this.labelSelection.classed('active-path', (d) => hasPathFocus && this.pathLinkKeys.has(d.key));
      this.labelSelection.classed('dimmed', (d) => {
        if (hasPathFocus) {
          return !this.pathLinkKeys.has(d.key);
        }
        return focusIds.size > 0 && !(d.source.id === this.selectedNodeId || d.target.id === this.selectedNodeId || d.source.id === this.highlightNodeId || d.target.id === this.highlightNodeId);
      });
    }
  }

  _stopSimulation() {
    if (this.simulation) {
      this.simulation.stop();
      this.simulation = null;
    }
  }

  _getWidth() {
    return this.svg.node().clientWidth || 1200;
  }

  _getHeight() {
    return this.svg.node().clientHeight || 800;
  }
}
