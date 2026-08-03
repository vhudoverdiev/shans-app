(function () {
    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";

    function createSvgElement(name, attributes, text) {
        const element = document.createElementNS(SVG_NS, name);
        Object.entries(attributes || {}).forEach(function (entry) {
            element.setAttribute(entry[0], String(entry[1]));
        });
        if (typeof text === "string") {
            element.textContent = text;
        }
        return element;
    }

    function formatDate(value) {
        const parts = String(value).split("-");
        if (parts.length !== 3) return value;
        return parts[2] + "." + parts[1];
    }

    function formatWeight(value) {
        return Number(value).toLocaleString("ru-RU", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
        });
    }

    function renderWeightChart() {
        const container = document.getElementById("weight-chart");
        const dataElement = document.getElementById("weight-chart-data");
        if (!container || !dataElement) return;

        let points;
        try {
            points = JSON.parse(dataElement.textContent || "[]");
        } catch (error) {
            points = [];
        }
        points = points
            .map(function (point) {
                return {
                    date: String(point.date || ""),
                    timestamp: Date.parse(String(point.date || "") + "T00:00:00"),
                    weight: Number(point.weight),
                };
            })
            .filter(function (point) {
                return point.date && Number.isFinite(point.timestamp) && Number.isFinite(point.weight);
            });

        if (!points.length) return;

        container.textContent = "";
        container.classList.add("weight-chart-scroll");

        const width = Math.max(620, container.clientWidth || 0, 150 + points.length * 82);
        const height = 320;
        const padding = { top: 38, right: 38, bottom: 54, left: 58 };
        const plotWidth = width - padding.left - padding.right;
        const plotHeight = height - padding.top - padding.bottom;
        const weights = points.map(function (point) { return point.weight; });
        const rawMinimum = Math.min.apply(null, weights);
        const rawMaximum = Math.max.apply(null, weights);
        const span = Math.max(rawMaximum - rawMinimum, 1);
        const minimum = Math.floor((rawMinimum - span * 0.18) * 2) / 2;
        const maximum = Math.ceil((rawMaximum + span * 0.18) * 2) / 2;
        const weightRange = Math.max(maximum - minimum, 1);
        const firstTimestamp = points[0].timestamp;
        const lastTimestamp = points[points.length - 1].timestamp;
        const timeRange = Math.max(lastTimestamp - firstTimestamp, 1);

        function xPosition(point, index) {
            if (points.length === 1) return padding.left + plotWidth / 2;
            if (lastTimestamp === firstTimestamp) {
                return padding.left + (index / (points.length - 1)) * plotWidth;
            }
            return padding.left + ((point.timestamp - firstTimestamp) / timeRange) * plotWidth;
        }

        function yPosition(point) {
            return padding.top + ((maximum - point.weight) / weightRange) * plotHeight;
        }

        const svg = createSvgElement("svg", {
            viewBox: "0 0 " + width + " " + height,
            width: width,
            height: height,
            "aria-hidden": "true",
            focusable: "false",
        });
        svg.style.width = width + "px";

        const defs = createSvgElement("defs");
        const lineGradient = createSvgElement("linearGradient", {
            id: "weight-line-gradient",
            x1: "0%",
            y1: "0%",
            x2: "100%",
            y2: "0%",
        });
        lineGradient.appendChild(createSvgElement("stop", {
            offset: "0%",
            "stop-color": "#2563eb",
        }));
        lineGradient.appendChild(createSvgElement("stop", {
            offset: "100%",
            "stop-color": "#7c3aed",
        }));
        const areaGradient = createSvgElement("linearGradient", {
            id: "weight-area-gradient",
            x1: "0%",
            y1: "0%",
            x2: "0%",
            y2: "100%",
        });
        areaGradient.appendChild(createSvgElement("stop", {
            offset: "0%",
            "stop-color": "#6366f1",
            "stop-opacity": "0.25",
        }));
        areaGradient.appendChild(createSvgElement("stop", {
            offset: "100%",
            "stop-color": "#6366f1",
            "stop-opacity": "0.01",
        }));
        defs.appendChild(lineGradient);
        defs.appendChild(areaGradient);
        svg.appendChild(defs);

        for (let index = 0; index <= 4; index += 1) {
            const ratio = index / 4;
            const y = padding.top + ratio * plotHeight;
            const labelValue = maximum - ratio * weightRange;
            svg.appendChild(createSvgElement("line", {
                x1: padding.left,
                x2: width - padding.right,
                y1: y,
                y2: y,
                class: "weight-chart-grid-line",
            }));
            svg.appendChild(createSvgElement("text", {
                x: padding.left - 12,
                y: y + 4,
                "text-anchor": "end",
                class: "weight-chart-axis-label",
            }, formatWeight(labelValue)));
        }

        const coordinates = points.map(function (point, index) {
            return {
                x: xPosition(point, index),
                y: yPosition(point),
                point: point,
            };
        });
        const linePoints = coordinates.map(function (item) {
            return item.x + "," + item.y;
        }).join(" ");
        const areaPoints = [
            padding.left + "," + (padding.top + plotHeight),
            linePoints,
            (width - padding.right) + "," + (padding.top + plotHeight),
        ].join(" ");

        svg.appendChild(createSvgElement("polygon", {
            points: areaPoints,
            class: "weight-chart-area",
        }));
        svg.appendChild(createSvgElement("polyline", {
            points: linePoints,
            class: "weight-chart-line",
        }));

        const labelIndexes = new Set([0, points.length - 1]);
        if (points.length > 2) {
            labelIndexes.add(Math.floor((points.length - 1) / 2));
        }
        if (points.length <= 6) {
            points.forEach(function (_point, index) { labelIndexes.add(index); });
        }

        coordinates.forEach(function (item, index) {
            const group = createSvgElement("g");
            const dot = createSvgElement("circle", {
                cx: item.x,
                cy: item.y,
                r: 5.5,
                class: "weight-chart-dot",
            });
            dot.appendChild(createSvgElement(
                "title",
                {},
                item.point.date + ": " + formatWeight(item.point.weight) + " кг"
            ));
            group.appendChild(dot);
            group.appendChild(createSvgElement("text", {
                x: item.x,
                y: item.y - 13,
                "text-anchor": "middle",
                class: "weight-chart-value",
            }, formatWeight(item.point.weight)));
            if (labelIndexes.has(index)) {
                group.appendChild(createSvgElement("text", {
                    x: item.x,
                    y: height - 22,
                    "text-anchor": "middle",
                    class: "weight-chart-axis-label",
                }, formatDate(item.point.date)));
            }
            svg.appendChild(group);
        });

        container.appendChild(svg);
        container.setAttribute(
            "aria-label",
            "График изменения веса: от " + formatWeight(points[0].weight)
                + " до " + formatWeight(points[points.length - 1].weight) + " килограмм"
        );
    }

    window.ShansWorkouts = window.ShansWorkouts || {};
    window.ShansWorkouts.renderWeightChart = renderWeightChart;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", renderWeightChart);
    } else {
        renderWeightChart();
    }

    document.addEventListener("shans:ajax-updated", function () {
        renderWeightChart();
    });
}());
