(function () {
  var canvas = document.getElementById("run-canvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var scoreEl = document.getElementById("run-score");
  var hiEl = document.getElementById("run-hi");
  var overEl = document.getElementById("run-over");
  var overScore = document.getElementById("run-over-score");
  var retryBtn = document.getElementById("run-retry");
  var pauseEl = document.getElementById("run-pause");
  var pauseBtn = document.getElementById("run-pause-btn");
  var resumeBtn = document.getElementById("run-resume");
  var hintEl = document.getElementById("run-hint");

  var W = 1600;
  var H = 640;
  var dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  var GROUND = H - 72;
  var CEIL = 36;
  var HI_KEY = "frensy-run-hi";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var hi = parseInt(localStorage.getItem(HI_KEY) || "0", 10) || 0;
  if (hiEl) hiEl.textContent = String(hi);

  var state = "idle";
  var phase = "angel";
  var t = 0;
  var scoreTicks = 0;
  var score = 0;
  var peak = 0;
  var speed = 7.4;
  var player;
  var obstacles = [];
  var spawnIn = 70;
  var flyHold = false;
  var invuln = 0;
  var flash = 0;
  var stab = 0;

  var ASSET_V = "5";
  var sheetBase = "/static/images/run/sheets/";
  var SPRITE_H = 128;
  var SPRITE_W = 102;

  var IMP_JUMP = [
    { speed: 5 },
    { speed: 7 },
    { speed: 6 },
  ];
  var CHERUB_ANIM = [
    { speed: 7 },
    { speed: 14 },
    { speed: 10 },
  ];

  var sheets = {
    angel: loadSheet(sheetBase + "angel-fly.png?v=" + ASSET_V, 4),
    impA: loadSheet(sheetBase + "imp-jump-a.png?v=" + ASSET_V, 4),
    impB: loadSheet(sheetBase + "imp-jump-b.png?v=" + ASSET_V, 4),
    impC: loadSheet(sheetBase + "imp-jump-c.png?v=" + ASSET_V, 4),
    cherubFly: loadSheet(sheetBase + "cherub-fly.png?v=" + ASSET_V, 4),
    cherubStand: loadSheet(sheetBase + "cherub-stand.png?v=" + ASSET_V, 4),
    cherubBack: loadSheet(sheetBase + "cherub-back.png?v=" + ASSET_V, 4),
    demon: loadSheet(sheetBase + "demon-stab.png?v=" + ASSET_V, 4),
  };

  function loadImg(src) {
    var im = new Image();
    im.src = src;
    return im;
  }

  function loadSheet(src, frames) {
    return { img: loadImg(src), frames: frames || 4 };
  }

  function impSheet(variant) {
    if (variant === 1) return sheets.impB;
    if (variant === 2) return sheets.impC;
    return sheets.impA;
  }

  function cherubSheet(variant) {
    if (variant === 1) return sheets.cherubStand;
    if (variant === 2) return sheets.cherubBack;
    return sheets.cherubFly;
  }

  function drawSheetFrame(sheet, frame, x, y, w, h, flipX) {
    var im = sheet && sheet.img;
    if (!im || !im.complete || !im.naturalWidth) return false;
    var fw = im.naturalWidth / sheet.frames;
    var fh = im.naturalHeight;
    var sx = frame * fw;
    ctx.save();
    if (flipX) {
      ctx.translate(x + w, y);
      ctx.scale(-1, 1);
      ctx.drawImage(im, sx, 0, fw, fh, 0, 0, w, h);
    } else {
      ctx.drawImage(im, sx, 0, fw, fh, x, y, w, h);
    }
    ctx.restore();
    return true;
  }

  function idleHint() {
    return "Удерживай пробел / клик — лететь · P — пауза";
  }

  function setHint() {
    if (!hintEl) return;
    if (state === "idle") hintEl.textContent = idleHint();
    else if (phase === "demon")
      hintEl.textContent = "чертенок · клик — трезубец в ангелочка · счёт вниз";
    else hintEl.textContent = "ангелочек летит · облетай чертят";
  }

  function showScore() {
    if (scoreEl) scoreEl.textContent = String(score);
  }

  function angelX() {
    return 110;
  }

  function demonX() {
    return W - 168;
  }

  function resetPlayer() {
    player = {
      x: angelX(),
      y: H * 0.34,
      w: SPRITE_W,
      h: SPRITE_H,
      vy: 0,
      onGround: false,
    };
  }

  function aabb(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function spawn() {
    var fromLeft = phase === "demon";
    var w = SPRITE_W;
    var h = SPRITE_H;
    var baseY = GROUND - h;
    obstacles.push({
      kind: phase === "demon" ? "cherub" : "imp",
      x: fromLeft ? -w - 24 : W + 24,
      y: baseY,
      baseY: baseY,
      w: w,
      h: h,
      anim: Math.floor(Math.random() * 3),
      seed: Math.floor(Math.random() * 100),
      frame: 0,
    });
    spawnIn = 70 + Math.floor(Math.random() * 64);
  }

  function animateObstacles() {
    obstacles.forEach(function (o) {
      if (o.kind === "imp") {
        var spec = IMP_JUMP[o.anim] || IMP_JUMP[0];
        var spd = reduce ? spec.speed + 2 : spec.speed;
        o.frame = Math.floor((t + o.seed) / spd) % 4;
        o.y = o.baseY;
      } else if (o.kind === "cherub") {
        var cspec = CHERUB_ANIM[o.anim] || CHERUB_ANIM[0];
        var cspd = reduce ? cspec.speed + 3 : cspec.speed;
        o.frame = Math.floor((t + o.seed) / cspd) % 4;
        o.y = o.baseY;
      }
    });
  }

  function angelFrame() {
    return reduce ? Math.floor(t / 8) % 4 : Math.floor(t / 4) % 4;
  }

  function demonFrame() {
    if (stab <= 0) return 0;
    return Math.min(3, Math.floor((18 - stab) / 5));
  }

  function setFly(on) {
    flyHold = on;
  }

  function actDown() {
    if (state === "paused") {
      resume();
      return;
    }
    if (state === "idle" || state === "over") {
      start();
      if (phase === "angel") setFly(true);
      return;
    }
    if (state !== "run") return;
    if (phase === "angel") setFly(true);
    else if (stab <= 0) stab = 18;
  }

  function actUp() {
    setFly(false);
  }

  function start() {
    state = "run";
    phase = "angel";
    t = 0;
    scoreTicks = 0;
    score = 0;
    peak = 0;
    invuln = 0;
    flash = 0;
    stab = 0;
    flyHold = false;
    speed = reduce ? 5.2 : 7.4;
    obstacles = [];
    spawnIn = 50;
    resetPlayer();
    if (overEl) overEl.hidden = true;
    if (pauseEl) pauseEl.hidden = true;
    setHint();
    showScore();
  }

  function becomeDemon(hit) {
    phase = "demon";
    invuln = 55;
    flash = 18;
    stab = 0;
    flyHold = false;
    player.x = demonX();
    player.w = SPRITE_W;
    player.h = SPRITE_H;
    player.y = GROUND - player.h;
    player.vy = 0;
    player.onGround = true;
    if (hit) {
      var i = obstacles.indexOf(hit);
      if (i >= 0) obstacles.splice(i, 1);
    }
    for (var j = 0; j < obstacles.length; j++) {
      obstacles[j].kind = "cherub";
      obstacles[j].x = W - obstacles[j].x - obstacles[j].w;
      obstacles[j].w = SPRITE_W;
      obstacles[j].h = SPRITE_H;
      obstacles[j].baseY = GROUND - obstacles[j].h;
      obstacles[j].y = obstacles[j].baseY;
      obstacles[j].seed = Math.floor(Math.random() * 100);
      obstacles[j].frame = 0;
    }
    setHint();
  }

  function rememberHi() {
    if (peak > hi) {
      hi = peak;
      localStorage.setItem(HI_KEY, String(hi));
      if (hiEl) hiEl.textContent = String(hi);
    }
  }

  function finish(label) {
    state = "over";
    rememberHi();
    if (overScore) overScore.textContent = (label || "пик") + " " + peak;
    if (overEl) overEl.hidden = false;
    if (pauseEl) pauseEl.hidden = true;
  }

  function hitObstacle(obs) {
    if (invuln > 0) return;
    if (phase === "angel") becomeDemon(obs);
    else finish("сошёл");
  }

  function stabBox() {
    var f = demonFrame();
    var reach = f >= 2 ? 130 : 90;
    return {
      x: player.x - reach,
      y: player.y + player.h * 0.32,
      w: reach + 10,
      h: 40,
    };
  }

  function pause() {
    if (state !== "run") return;
    state = "paused";
    flyHold = false;
    if (pauseEl) pauseEl.hidden = false;
  }

  function resume() {
    if (state !== "paused") return;
    state = "run";
    if (pauseEl) pauseEl.hidden = true;
  }

  function togglePause() {
    if (state === "run") pause();
    else if (state === "paused") resume();
  }

  function drawGround() {
    ctx.strokeStyle = "rgba(220,228,236,0.45)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, GROUND + 0.5);
    ctx.lineTo(W, GROUND + 0.5);
    ctx.stroke();
    var dir = phase === "demon" ? -1 : 1;
    var g = ((t * speed * 0.4 * dir) % 36 + 36) % 36;
    ctx.strokeStyle = "rgba(180,196,216,0.18)";
    for (var x = -g; x < W; x += 36) {
      ctx.beginPath();
      ctx.moveTo(x, GROUND + 8);
      ctx.lineTo(x + 14, GROUND + 8);
      ctx.stroke();
    }
  }

  function drawAngelFallback(x, y, flap) {
    var beat = Math.sin(flap) * 8;
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "#e8eef6";
    ctx.beginPath();
    ctx.ellipse(36, 28, 16, 14, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(220,228,238,0.32)";
    ctx.beginPath();
    ctx.ellipse(8, 34 - beat, 22, 20, -0.35, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(64, 34 + beat, 22, 20, 0.35, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawPlayer() {
    if (flash > 0 && flash % 4 < 2) return;
    var pw = SPRITE_W + 8;
    var ph = SPRITE_H + 4;
    if (phase === "demon") {
      if (
        !drawSheetFrame(
          sheets.demon,
          demonFrame(),
          player.x - 6,
          player.y - 2,
          pw,
          ph,
          false
        )
      ) {
        drawAngelFallback(player.x, player.y, t * 0.18);
      }
    } else if (
      !drawSheetFrame(
        sheets.angel,
        angelFrame(),
        player.x - 6,
        player.y - 2,
        pw,
        ph,
        false
      )
    ) {
      drawAngelFallback(player.x, player.y, t * 0.18);
    }
  }

  function drawObstacle(o) {
    drawSheetFrame(
      o.kind === "cherub" ? cherubSheet(o.anim) : impSheet(o.anim),
      o.frame || 0,
      o.x,
      o.y,
      o.w,
      o.h,
      false
    );
  }

  function physicsAngel() {
    var grav = reduce ? 0.28 : 0.42;
    var lift = reduce ? 0.55 : 0.78;
    if (flyHold) player.vy -= lift;
    player.vy += grav;
    if (player.vy > 9) player.vy = 9;
    if (player.vy < -8.5) player.vy = -8.5;
    player.y += player.vy;
    if (player.y < CEIL) {
      player.y = CEIL;
      player.vy = 0;
    }
    if (player.y + player.h > GROUND) {
      player.y = GROUND - player.h;
      player.vy *= -0.35;
    }
  }

  function physicsDemon() {
    var grav = 0.85;
    player.vy += grav;
    player.y += player.vy;
    if (player.y + player.h >= GROUND) {
      player.y = GROUND - player.h;
      player.vy = 0;
      player.onGround = true;
    } else player.onGround = false;
    if (stab > 0) {
      stab -= 1;
      var box = stabBox();
      for (var s = obstacles.length - 1; s >= 0; s--) {
        if (aabb(box, obstacles[s])) obstacles.splice(s, 1);
      }
    }
  }

  function physics() {
    t += 1;
    speed = Math.min(reduce ? 8 : 13.5, speed + 0.0016);
    if (phase === "angel") scoreTicks += 1;
    else scoreTicks -= 1;
    score = Math.max(0, Math.floor(scoreTicks / 5));
    if (score > peak) peak = score;
    showScore();
    if (phase === "demon" && scoreTicks <= 0) {
      finish("дошёл до нуля");
      return;
    }

    spawnIn -= 1;
    if (spawnIn <= 0) spawn();
    if (invuln > 0) invuln -= 1;
    if (flash > 0) flash -= 1;

    animateObstacles();

    if (phase === "angel") physicsAngel();
    else physicsDemon();

    var dir = phase === "demon" ? 1 : -1;
    for (var i = obstacles.length - 1; i >= 0; i--) {
      obstacles[i].x += speed * dir;
      var gone =
        phase === "demon"
          ? obstacles[i].x > W + 20
          : obstacles[i].x + obstacles[i].w < -20;
      if (gone) obstacles.splice(i, 1);
      else if (aabb(player, obstacles[i])) {
        hitObstacle(obstacles[i]);
        break;
      }
    }
  }

  function tick() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#050505";
    ctx.fillRect(0, 0, W, H);
    drawGround();

    if (state === "idle") {
      phase = "angel";
      resetPlayer();
      player.y = H * 0.34 + Math.sin(performance.now() / 420) * 8;
      drawPlayer();
      requestAnimationFrame(tick);
      return;
    }

    if (state === "run") physics();

    obstacles.forEach(drawObstacle);
    drawPlayer();
    requestAnimationFrame(tick);
  }

  if (pauseBtn) {
    pauseBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      togglePause();
    });
  }
  if (resumeBtn) {
    resumeBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      resume();
    });
  }

  window.addEventListener("keydown", function (e) {
    if (e.code === "KeyP" || e.code === "Escape") {
      e.preventDefault();
      togglePause();
      return;
    }
    if (e.code === "Space" || e.code === "ArrowUp") {
      e.preventDefault();
      actDown();
    }
  });
  window.addEventListener("keyup", function (e) {
    if (e.code === "Space" || e.code === "ArrowUp") actUp();
  });
  canvas.addEventListener("pointerdown", function () {
    actDown();
  });
  window.addEventListener("pointerup", function () {
    actUp();
  });
  if (retryBtn) {
    retryBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      start();
    });
  }

  resetPlayer();
  setHint();
  requestAnimationFrame(tick);
})();
