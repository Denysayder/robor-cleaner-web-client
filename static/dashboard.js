// static/dashboard.js
document.addEventListener("DOMContentLoaded", () => {
    const modal      = new bootstrap.Modal(document.getElementById("locationModal"));
    const latInput   = document.getElementById("latInput");
    const lonInput   = document.getElementById("lonInput");
    const storedLat  = localStorage.getItem("lat");
    const storedLon  = localStorage.getItem("lon");
    if (storedLat) latInput.value = storedLat;
    if (storedLon) lonInput.value = storedLon;
    const ctx = document.getElementById("energyChart").getContext("2d");
    let energyChart = null;

    async function loadChartData() {
        const res = await fetch("/api/chart-data");
        if (!res.ok) return;
        const data = await res.json();
        if (energyChart) {
            energyChart.data.labels = data.labels;
            data.datasets.forEach((d, i) => {
                energyChart.data.datasets[i].data = d.data;
            });
            energyChart.update();
        } else {
            energyChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: data.labels,
                    datasets: data.datasets.map(ds => ({
                        label: ds.label,
                        data: ds.data,
                        fill: false,
                        tension: 0.3,
                        borderWidth: 2,
                        pointRadius: 2,
                    })),
                },
                options: {
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { autoSkip: true, maxTicksLimit: 8 } },
                        y: { beginAtZero: true },
                    },
                    plugins: { legend: { display: true } },
                },
            });
        }
    }

    async function loadWeather() {
        const lat = latInput.value || storedLat || "50.4501";
        const lon = lonInput.value || storedLon || "30.5234";
        const res = await fetch(`/api/weather?lat=${lat}&lon=${lon}`);
        if (!res.ok) return;
        const data = await res.json();
        const list = document.getElementById("weatherList");
        list.innerHTML = "";

        const header = document.createElement("li");
        header.className = "list-group-item active";
        header.textContent = `${lat}, ${lon} – ${new Date(data.hourly.time[0]).toLocaleDateString()}`;
        list.appendChild(header);

        const { time, temperature_2m, precipitation_probability } = data.hourly;
        for (let i = 0; i < time.length; i += 3) {
            const li = document.createElement("li");
            li.className = "list-group-item d-flex justify-content-between";
            const t = new Date(time[i]);
            li.innerHTML = `
                <span>${t.getHours().toString().padStart(2,"0")}:00</span>
                <span>${temperature_2m[i]}°C</span>
                <span>${precipitation_probability[i]}%</span>`;
            list.appendChild(li);
            if (i >= 21) break;
        }
    }


    function sendRobotCommand(cmd) {
        return fetch("/api/robot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: cmd }),
        });
    }

    document.getElementById("refreshChart").addEventListener("click", loadChartData);
    document.getElementById("refreshWeather").addEventListener("click", loadWeather);

    document.querySelectorAll(".robot-cmd").forEach(btn => {
        btn.addEventListener("click", async () => {
        const cmd = btn.dataset.cmd;

        try {
            const resp = await fetch("/api/robot", {
            method : "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept"      : "application/json"
            },
            body   : JSON.stringify({ command: cmd })
            });

            if (!resp.ok) {
            throw new Error(await resp.text());
            }
        } catch (err) {
            confirm("Error");
            console.error(err);
            alert(`Ошибка: ${err.message}`);
        }
        });
    });

    loadChartData();
    loadWeather();
    
    document.getElementById("editLocation").addEventListener("click", () => modal.show());

    document.getElementById("saveLocation").addEventListener("click", () => {
        localStorage.setItem("lat",  latInput.value);
        localStorage.setItem("lon",  lonInput.value);
        modal.hide();
        loadWeather();
    });

});
