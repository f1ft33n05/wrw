(function () {
  const canvas = document.getElementById("sales-chart");
  if (!canvas) return;

  const data = JSON.parse(document.getElementById("sales-chart-data").textContent || "[]");

  function draw() {
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, rect.width * ratio);
    canvas.height = Math.max(1, rect.height * ratio);

    const context = canvas.getContext("2d");
    context.scale(ratio, ratio);
    context.clearRect(0, 0, rect.width, rect.height);

    const compact = rect.width < 700;
    const padding = { top: 20, right: 16, bottom: 48, left: compact ? 52 : 68 };
    const chartWidth = rect.width - padding.left - padding.right;
    const chartHeight = rect.height - padding.top - padding.bottom;
    const values = data.map((point) => Number(point.total) || 0);
    const maxValue = Math.max(...values, 0);
    const step = maxValue <= 0 ? 1000 : Math.pow(10, Math.floor(Math.log10(maxValue)));
    const axisMax = maxValue <= 0 ? step : Math.ceil(maxValue / (step / 2)) * (step / 2);
    const gridCount = 5;

    context.font = "11px Arial";
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (let index = 0; index <= gridCount; index++) {
      const y = padding.top + chartHeight - (chartHeight * index / gridCount);
      const value = axisMax * index / gridCount;
      context.strokeStyle = "rgba(155, 164, 174, .25)";
      context.beginPath();
      context.moveTo(padding.left, y);
      context.lineTo(rect.width - padding.right, y);
      context.stroke();
      context.fillStyle = "#667085";
      context.fillText(formatValue(value), padding.left - 9, y);
    }

    context.textAlign = "center";
    context.textBaseline = "top";
    const xStep = data.length > 1 ? chartWidth / (data.length - 1) : chartWidth;
    const labelEvery = compact ? Math.ceil(data.length / 8) : Math.ceil(data.length / 14);
    context.beginPath();
    data.forEach((point, index) => {
      const x = data.length === 1 ? padding.left + chartWidth / 2 : padding.left + index * xStep;
      const y = padding.top + chartHeight - ((Number(point.total) || 0) / (axisMax || 1) * chartHeight);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.strokeStyle = "#8e83e8";
    context.lineWidth = 2;
    context.stroke();

    data.forEach((point, index) => {
      const x = data.length === 1 ? padding.left + chartWidth / 2 : padding.left + index * xStep;
      const y = padding.top + chartHeight - ((Number(point.total) || 0) / (axisMax || 1) * chartHeight);
      context.fillStyle = "#8e83e8";
      context.beginPath();
      context.arc(x, y, 3.5, 0, Math.PI * 2);
      context.fill();
      if (index % labelEvery === 0 || index === data.length - 1) {
        context.save();
        context.translate(x, padding.top + chartHeight + 9);
        context.rotate(-Math.PI / 4);
        context.fillStyle = "#667085";
        context.fillText(formatDate(point.date), 0, 0);
        context.restore();
      }
    });
  }

  function formatDate(value) {
    const date = new Date(value + "T00:00:00");
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }

  function formatValue(value) {
    if (value >= 1000000) return (value / 1000000).toFixed(1) + "m";
    if (value >= 1000) return (value / 1000).toFixed(value >= 10000 ? 0 : 1) + "k";
    return Math.round(value).toString();
  }

  window.addEventListener("resize", draw);
  draw();
})();
