const playerProfile = document.getElementById('playerProfile');
const backToPlayers = document.getElementById('backToPlayers');
const playerId = new URLSearchParams(window.location.search).get('player');
const players = Array.isArray(window.playerProfiles) ? window.playerProfiles : [];
const player = players.find((entry) => entry.id === playerId) || null;

function safeImage(image, title) {
  const img = new Image();
  img.src = image;
  img.alt = title;
  img.loading = 'eager';
  img.onerror = function () {
    this.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 800 1000%22%3E%3Crect width=%22800%22 height=%221000%22 fill=%22%230b3a8c%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 fill=%22white%22 text-anchor=%22middle%22 font-size=%2248%22 font-family=%22Arial%22%3E' + encodeURIComponent(title) + '%3C/text%3E%3C/svg%3E';
  };
  return img;
}

function formatValue(value) {
  return value === null || value === undefined || value === '' ? 'Data unavailable' : value;
}

function renderStatsRow(formatName, stats) {
  return `
    <tr>
      <th scope="row">${formatName}</th>
      <td>${formatValue(stats.matches)}</td>
      <td>${formatValue(stats.runs)}</td>
      <td>${formatValue(stats.wickets)}</td>
      <td>${formatValue(stats.highScore)}</td>
      <td>${formatValue(stats.average)}</td>
    </tr>
  `;
}

function renderPlayer() {
  if (!playerProfile) return;

  if (!player) {
    playerProfile.innerHTML = `
      <div class="profile-not-found">
        <h1>Player profile not found</h1>
        <p>The requested player is not available in this World Cup 2027 selection.</p>
        <a class="primary-button" href="index.html#players">Back to Players</a>
      </div>
    `;
    return;
  }

  const image = safeImage(player.photo, player.name);
  image.className = 'profile-photo';
  playerProfile.innerHTML = `
    <div class="profile-header card">
      <div class="profile-photo-wrap">${image.outerHTML}</div>
      <div class="profile-intro">
        <p class="eyebrow dark">India's Predicted Playing XI</p>
        <h1>${player.name}</h1>
        <p class="player-role large">#${player.number} · ${player.role}</p>
        <p class="profile-bio">${player.bio}</p>
        <div class="profile-badges">
          <span>${player.battingStyle}</span>
          <span>${player.bowlingStyle}</span>
        </div>
      </div>
    </div>

    <section class="profile-details card">
      <div class="section-heading compact">
        <div><p class="eyebrow dark">Player information</p><h2>Career overview</h2></div>
      </div>
      <dl class="player-facts">
        <div><dt>Full name</dt><dd>${player.name}</dd></div>
        <div><dt>Date of birth</dt><dd>${formatValue(player.dateOfBirth)}</dd></div>
        <div><dt>Age</dt><dd>${formatValue(player.age)}</dd></div>
        <div><dt>Birthplace</dt><dd>${formatValue(player.birthplace)}</dd></div>
        <div><dt>Batting style</dt><dd>${formatValue(player.battingStyle)}</dd></div>
        <div><dt>Bowling style</dt><dd>${formatValue(player.bowlingStyle)}</dd></div>
        <div><dt>Playing role</dt><dd>${formatValue(player.role)}</dd></div>
      </dl>
    </section>

    <section class="profile-details card">
      <div class="section-heading compact">
        <div><p class="eyebrow dark">International career</p><h2>Highlights</h2></div>
      </div>
      <ul class="highlight-list">
        ${player.highlights.map((highlight) => `<li>${highlight}</li>`).join('')}
      </ul>
    </section>

    <section class="stats-section card">
      <div class="section-heading compact">
        <div><p class="eyebrow dark">Cricket career statistics</p><h2>International records</h2></div>
      </div>
      <div class="stats-table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Format</th>
              <th scope="col">Matches</th>
              <th scope="col">Runs</th>
              <th scope="col">Wickets</th>
              <th scope="col">Highest score</th>
              <th scope="col">Average</th>
            </tr>
          </thead>
          <tbody>
            ${renderStatsRow('Test', player.stats.tests)}
            ${renderStatsRow('ODI', player.stats.odi)}
            ${renderStatsRow('T20I', player.stats.t20i)}
          </tbody>
        </table>
      </div>
      <div class="stat-summary">
        <article><span>Centuries</span><strong>${formatValue(player.centuries)}</strong></article>
        <article><span>Half-centuries</span><strong>${formatValue(player.halfCenturies)}</strong></article>
        <article><span>Batting strike rate</span><strong>${formatValue(player.batStrikeRate)}</strong></article>
        <article><span>Bowling economy rate</span><strong>${formatValue(player.bowlingEconomy)}</strong></article>
        <article><span>Best bowling figures</span><strong>${formatValue(player.bestBowling)}</strong></article>
        <article><span>Career achievements</span><strong>${formatValue(player.achievements)}</strong></article>
      </div>
      <p class="stats-note">Career statistics are shown exactly as verified in the local source data. Statistics with no verified value are shown as “Data unavailable.” Last updated: ${player.lastUpdated}.</p>
    </section>
  `;

  if (backToPlayers) {
    backToPlayers.href = 'index.html#players';
  }
}

renderPlayer();
