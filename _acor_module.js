      /* MODO_ANALISIS_CORRELACIONAL_AB */
      let acorLastExport = null;
      let acorLastHypothesisResult = null;
      let acorLastRegs = null;
      let acorLastRows = null;
      let acorLastPatronesDominantes = null;
      let acorLastRelacionesCruzadas = null;
      let acorLastRankingHipotesis = null;
      let acorLastCoincidenciasBusqueda = null;
      let acorHipotesisColaExperimental = [];

      function acorFetchMaestro() {
        if (typeof fetch !== "function") return Promise.reject(new Error("sin fetch"));
        return fetch("historicos_maestro.json", { cache: "no-store" })
          .then(function (r) {
            if (!r.ok) throw new Error("no maestro");
            return r.json();
          })
          .then(function (payload) {
            const regs =
              payload && Array.isArray(payload.registros)
                ? payload.registros
                : Array.isArray(payload)
                  ? payload
                  : [];
            return { meta: payload && payload._meta ? payload._meta : null, registros: regs, raw: payload };
          });
      }

      function acorDigitsFromSeed4(s4) {
        const x = sanitize4(s4);
        if (!/^\d{4}$/.test(x)) return null;
        return x.split("").map(Number);
      }

      function acorDigitsFromEq3(eq) {
        const x = sanitize3(eq);
        if (!/^\d{3}$/.test(x)) return null;
        return x.split("").map(Number);
      }

      function acorPairFromInicio(v) {
        const p = padTwoInicio(v);
        if (!p) return null;
        return [Number(p[0]), Number(p[1])];
      }

      function acorEvalSafe(expr, vars) {
        let e = String(expr).trim();
        e = e.replace(/\babs\s*\(/gi, "Math.abs(");
        const keys = Object.keys(vars).sort(function (a, b) {
          return b.length - a.length;
        });
        keys.forEach(function (k) {
          if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(k)) return;
          const val = vars[k];
          const num = Number(val);
          if (!Number.isFinite(num)) return;
          e = e.replace(new RegExp("\\b" + k + "\\b", "g"), "(" + num + ")");
        });
        if (!/^[-+*/().%\s0-9Math]+$/.test(e)) {
          throw new Error("expresión con símbolo no permitido");
        }
        return Function('"use strict"; return (' + e + ")")();
      }

      function acorEvalDiscoveryExpr(expr, vars) {
        let e = String(expr).trim().replace(/\u2212/g, "-");
        e = e.replace(/\babs\s*\(/gi, "Math.abs(");
        e = e.replace(/\bespejo\s*\(/gi, "espejoDig(");
        e = e.replace(/\bmod10\s*\(/gi, "mod10v(");
        const keys = Object.keys(vars).sort(function (a, b) {
          return b.length - a.length;
        });
        keys.forEach(function (k) {
          if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(k)) return;
          const val = vars[k];
          const num = Number(val);
          if (!Number.isFinite(num)) return;
          e = e.replace(new RegExp("\\b" + k + "\\b", "g"), "(" + num + ")");
        });
        if (/constructor|prototype|__proto__|Function|document|window/i.test(e)) {
          throw new Error("secuencia no permitida");
        }
        if (!/^[-+*/().%\s0-9Math_espejoDigmod10v,]+$/.test(e)) {
          throw new Error("expresión con símbolo no permitido (modo búsqueda)");
        }
        const pre =
          '"use strict"; function mod10v(x){return ((Math.round(Number(x))%10)+10)%10;} function espejoDig(x){var d=mod10v(x);var m={0:5,1:6,2:7,3:8,4:9,5:0,6:1,7:2,8:3,9:4};return m[d];} ';
        return Function(pre + "return (" + e + ");")();
      }

      function acorRunHypothesisLines(text, env0) {
        const vars = Object.assign({}, env0);
        const lines = String(text || "")
          .split(/\n/)
          .map(function (l) {
            return l.trim();
          })
          .filter(function (l) {
            return l && l[0] !== "#";
          });
        lines.forEach(function (line) {
          const eq = line.indexOf("=");
          if (eq < 0) return;
          const name = line.slice(0, eq).trim();
          const rhs = line.slice(eq + 1).trim();
          if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
            throw new Error("nombre inválido: " + name);
          }
          vars[name] = acorEvalSafe(rhs, vars);
        });
        return vars;
      }

      function acorHypothesisMatchRecord(text, rec) {
        const sDig = acorDigitsFromSeed4(rec.semilla);
        const eDig = acorDigitsFromEq3(rec.equivalente);
        const abA = acorPairFromInicio(rec.inicioA);
        const abB = acorPairFromInicio(rec.inicioB);
        if (!sDig || !eDig || !abA || !abB) {
          return { evaluable: false, motivo: "faltan semilla, equivalente o inicios A/B completos" };
        }
        const s1 = sDig[0];
        const s2 = sDig[1];
        const s3 = sDig[2];
        const s4 = sDig[3];
        const e1 = eDig[0];
        const e2 = eDig[1];
        const e3 = eDig[2];
        const a1 = abA[0];
        const a2 = abA[1];
        const b1 = abB[0];
        const b2 = abB[1];
        const A_num = a1 * 10 + a2;
        const B_num = b1 * 10 + b2;
        const env0 = { s1: s1, s2: s2, s3: s3, s4: s4, e1: e1, e2: e2, e3: e3, a1: a1, a2: a2, b1: b1, b2: b2, A_num: A_num, B_num: B_num };
        let vars;
        try {
          vars = acorRunHypothesisLines(text, env0);
        } catch (err) {
          return { evaluable: false, error: String(err && err.message ? err.message : err) };
        }
        const checks = [];
        let okAll = true;
        const pairs = [
          ["a1p", "a1"],
          ["a2p", "a2"],
          ["b1p", "b1"],
          ["b2p", "b2"],
          ["Ap", "A_num"],
          ["Bp", "B_num"]
        ];
        pairs.forEach(function (pr) {
          const pk = pr[0];
          const base = pr[1];
          if (vars[pk] === undefined || env0[base] === undefined) return;
          const pred = Math.round(Number(vars[pk]));
          const act = Math.round(Number(env0[base]));
          const ok = pred === act;
          checks.push({ variable: pk, predicho: pred, actual: base + "=" + act, ok: ok });
          if (!ok) okAll = false;
        });
        Object.keys(vars).forEach(function (k) {
          if (k.length < 2 || k[k.length - 1] !== "p") return;
          if (pairs.some(function (pr) { return pr[0] === k; })) return;
          const base = k.slice(0, -1);
          if (!Object.prototype.hasOwnProperty.call(env0, base)) return;
          const pred = Math.round(Number(vars[k]));
          const act = Math.round(Number(env0[base]));
          const ok = pred === act;
          checks.push({ variable: k, predicho: pred, actual: base + "=" + act, ok: ok });
          if (!ok) okAll = false;
        });
        if (!checks.length) {
          return {
            evaluable: true,
            vars: vars,
            acierto: null,
            nota: "Defina predicciones con nombre terminado en «p» (ej. a1p) para comparar con a1."
          };
        }
        return { evaluable: true, acierto: okAll, checks: checks, vars: vars };
      }

      function acorInvertDigits(arr) {
        return arr ? arr.slice().reverse() : null;
      }

      function acorFreqDigits(arr) {
        const f = {};
        if (!arr) return f;
        arr.forEach(function (d) {
          f[d] = (f[d] || 0) + 1;
        });
        return f;
      }

      function acorRepeatedTriples(sArr) {
        if (!sArr || sArr.length < 3) return [];
        const out = [];
        for (let i = 0; i <= sArr.length - 3; i++) {
          out.push(sArr[i] + "_" + sArr[i + 1] + "_" + sArr[i + 2]);
        }
        return out;
      }

      function acorCorrelSeedEq(s, e) {
        if (!s || !e) return null;
        const abs = [];
        const mod = [];
        for (let j = 0; j < 3; j++) {
          abs.push(Math.abs(e[j] - s[j]));
          mod.push((e[j] - s[j] + 100) % 10);
        }
        const sumas = [s[0] + e[0], s[1] + e[1], s[2] + e[2], s[0] + e[1], s[1] + e[2]];
        const restas = [s[0] - e[0], s[1] - e[1], e[0] - s[1]];
        const rep = {};
        s.forEach(function (d) {
          rep[d] = (rep[d] || 0) + 1;
        });
        const reflejo = s[0] === s[3] && s[1] === s[2];
        const despl = [];
        for (let r = 1; r < 4; r++) {
          despl.push(s.slice(r).concat(s.slice(0, r)).join(""));
        }
        const inv = acorInvertDigits(s);
        const cons = [];
        for (let i = 0; i < s.length - 1; i++) {
          if ((s[i] + 1) % 10 === s[i + 1]) cons.push("s" + (i + 1) + "->s" + (i + 2));
        }
        const gem = s[0] === s[3] || Object.keys(rep).some(function (k) {
          return rep[k] > 1;
        });
        const digitBag = [];
        s.forEach(function (d, i) {
          digitBag.push({ t: "s" + (i + 1), d: d });
        });
        e.forEach(function (d, i) {
          digitBag.push({ t: "e" + (i + 1), d: d });
        });
        const espejo = [];
        const equiv = [];
        const esc = [];
        for (let u = 0; u < digitBag.length; u++) {
          for (let v = u + 1; v < digitBag.length; v++) {
            const a = digitBag[u].d;
            const b = digitBag[v].d;
            if (espejoMap[a] === b) espejo.push(digitBag[u].t + "~" + digitBag[v].t);
            if (equivalenciaMap[a] === b) equiv.push(digitBag[u].t + "~" + digitBag[v].t);
            if (tablaA[a] === b) esc.push(digitBag[u].t + "->" + digitBag[v].t);
          }
        }
        return {
          diferencias_abs_e_s: abs,
          diferencias_mod10_e_s: mod,
          sumas_cruzadas: sumas,
          restas_cruzadas: restas,
          repeticiones_semilla: rep,
          reflejo_s1s4_s2s3: reflejo,
          pares_espejo_semilla_equiv: espejo,
          pares_equivalencia: equiv,
          pares_escalera: esc,
          desplazamientos_circulares_lectura: despl,
          inversion_semilla: inv ? inv.join("") : null,
          pares_consecutivos_mod10: cons,
          cierres_gemelos_o_dup: gem,
          frecuencia_digitos_semilla: acorFreqDigits(s),
          triples_semilla: acorRepeatedTriples(s)
        };
      }

      function acorCorrelEqInicios(e, a2, b2) {
        if (!e || !a2 || !b2) return null;
        const pos = [];
        for (let i = 0; i < 2; i++) {
          pos.push({
            e_idx: i + 1,
            a: a2[i],
            e: e[i],
            igual: a2[i] === e[i],
            dist_mod10: (a2[i] - e[i] + 100) % 10
          });
        }
        const saltos = [(a2[0] - a2[1] + 100) % 10, (b2[0] - b2[1] + 100) % 10, (a2[0] - b2[0] + 100) % 10];
        const bag = [
          { t: "e1", d: e[0] },
          { t: "e2", d: e[1] },
          { t: "e3", d: e[2] },
          { t: "a1", d: a2[0] },
          { t: "a2", d: a2[1] },
          { t: "b1", d: b2[0] },
          { t: "b2", d: b2[1] }
        ];
        const espejo = [];
        const equiv = [];
        const esc = [];
        for (let u = 0; u < bag.length; u++) {
          for (let v = u + 1; v < bag.length; v++) {
            const x = bag[u].d;
            const y = bag[v].d;
            if (espejoMap[x] === y) espejo.push(bag[u].t + "~" + bag[v].t);
            if (equivalenciaMap[x] === y) equiv.push(bag[u].t + "~" + bag[v].t);
            if (tablaA[x] === y) esc.push(bag[u].t + "->" + bag[v].t);
          }
        }
        return {
          coincidencias_posicion_a_vs_eq: pos,
          saltos_mod10: saltos,
          pares_espejo: espejo,
          pares_equivalencia: equiv,
          pares_escalera: esc,
          familia_mod10_e1e2: (e[0] * 10 + e[1]) % 100,
          familia_mod10_a1a2: (a2[0] * 10 + a2[1]) % 100
        };
      }

      function acorCorrelCompleto(rec, env) {
        const s = env.sDig;
        const e = env.eDig;
        const g = env.gDig;
        const serA = env.serieA;
        const serB = env.serieB;
        const chA = env.chainA;
        const chB = env.chainB;
        const cuad = String(rec.cuadricula_real || "").trim();
        const out = {
          serieA_vs_semilla: serA.length
            ? serA.map(function (cell, i) {
                return { celda: i, valor: cell, igual_s1: String(cell) === String(s[0]) };
              })
            : [],
          serieB_vs_equiv: serB.length
            ? serB.map(function (cell, i) {
                return { celda: i, valor: cell, igual_e1: String(cell) === String(e[0]) };
              })
            : [],
          serieA_vs_chain_oficial: chA.length && serA.length === chA.length
            ? serA.map(function (c, i) {
                return String(c).replace(/\D/g, "").slice(-2).padStart(2, "0") === chA[i];
              })
            : null,
          serieB_vs_chain_oficial: chB.length && serB.length === chB.length
            ? serB.map(function (c, i) {
                return String(c).replace(/\D/g, "").slice(-2).padStart(2, "0") === chB[i];
              })
            : null,
          ganador_vs_semilla: g ? { comparte_digitos: g.filter(function (d) { return s.indexOf(d) >= 0; }) } : null,
          ganador_vs_equiv: g ? { comparte_digitos: g.filter(function (d) { return e.indexOf(d) >= 0; }) } : null,
          cuadricula_real_presente: cuad.length > 0
        };
        return out;
      }

      function acorBuildEnv(rec) {
        const sDig = acorDigitsFromSeed4(rec.semilla);
        const eDig = acorDigitsFromEq3(rec.equivalente);
        const g4 = ganadorFourFromRecord(rec);
        const gDig = /^\d{4}$/.test(g4) ? g4.split("").map(Number) : null;
        const abA = acorPairFromInicio(rec.inicioA);
        const abB = acorPairFromInicio(rec.inicioB);
        const serA = Array.isArray(rec.serieA) ? rec.serieA.map(String) : [];
        const serB = Array.isArray(rec.serieB) ? rec.serieB.map(String) : [];
        const ia = padTwoInicio(rec.inicioA);
        const ib = padTwoInicio(rec.inicioB);
        const chainA = ia ? buildCircularChainFromInicio(ia) : [];
        const chainB = ib ? buildCircularChainFromInicio(ib) : [];
        return {
          sDig: sDig,
          eDig: eDig,
          gDig: gDig,
          abA: abA,
          abB: abB,
          serieA: serA,
          serieB: serB,
          chainA: chainA,
          chainB: chainB
        };
      }

      function acorAnalyzeRecord(rec, idx) {
        const env = acorBuildEnv(rec);
        const s = env.sDig;
        const e = env.eDig;
        const g4 = ganadorFourFromRecord(rec);
        const A = acorCorrelSeedEq(s, e);
        const Bblock = env.eDig && env.abA && env.abB ? acorCorrelEqInicios(env.eDig, env.abA, env.abB) : null;
        const C = acorCorrelCompleto(rec, env);
        return {
          indice: idx + 1,
          sorteo: String(rec.sorteo || ""),
          semilla: sanitize4(rec.semilla),
          equivalente: sanitize3(rec.equivalente),
          inicioA: String(rec.inicioA || ""),
          inicioB: String(rec.inicioB || ""),
          ganador_real: g4 || "",
          cuadricula_real: String(rec.cuadricula_real || ""),
          serieA: Array.isArray(rec.serieA) ? rec.serieA : [],
          serieB: Array.isArray(rec.serieB) ? rec.serieB : [],
          A_semilla_equiv: A,
          B_equiv_inicios: Bblock,
          C_completo: C,
          env_digitos: {
            s1s2s3s4: s,
            e1e2e3: e,
            a1a2: env.abA,
            b1b2: env.abB,
            g1g2g3g4: env.gDig
          }
        };
      }

      function acorSerieCircularCoincide(rec, env, letra) {
        const ia = padTwoInicio(letra === "A" ? rec.inicioA : rec.inicioB);
        const ser = letra === "A" ? env.serieA : env.serieB;
        const ch = letra === "A" ? env.chainA : env.chainB;
        if (!ia || ser.length !== 6 || ch.length !== 6) return false;
        return ser.every(function (c, i) {
          return String(c).replace(/\D/g, "").slice(-2).padStart(2, "0") === ch[i];
        });
      }

      function acorPatternTags(row, env) {
        const tags = [];
        const s = env.sDig;
        const e = env.eDig;
        const abA = env.abA;
        const abB = env.abB;
        if (abA && abB) {
          const An = abA[0] * 10 + abA[1];
          const Bn = abB[0] * 10 + abB[1];
          if (An - Bn === 22 || Bn - An === 22) tags.push("AB_diff_22");
        }
        if (s) {
          const f = acorFreqDigits(s);
          if (Object.keys(f).some(function (k) { return f[k] > 1; })) tags.push("semilla_repite_digito");
          if (s[0] === s[3]) tags.push("semilla_s1_eq_s4");
        }
        if (s && e) {
          tags.push("mod10_e_vs_s_" + [0, 1, 2].map(function (j) { return (e[j] - s[j] + 100) % 10; }).join("_"));
        }
        if (abA && e && s) {
          if (abA[0] === Math.abs(e[0] - s[0])) tags.push("a1_eq_abs_e1_s1");
          if (abA[1] === e[1]) tags.push("a2_eq_e2");
        }
        if (acorSerieCircularCoincide(row, env, "A")) tags.push("serieA_igual_cadena_oficial");
        if (acorSerieCircularCoincide(row, env, "B")) tags.push("serieB_igual_cadena_oficial");
        return tags;
      }

      function acorPatronDescripcionLegible(patronId) {
        if (patronId === "AB_diff_22") return "A_num − B_num = 22 o B_num − A_num = 22";
        if (patronId === "semilla_repite_digito") return "La semilla repite al menos un dígito";
        if (patronId === "semilla_s1_eq_s4") return "s1 = s4 en la semilla";
        if (patronId === "a1_eq_abs_e1_s1") return "a1 = abs(e1 − s1)";
        if (patronId === "a2_eq_e2") return "a2 = e2";
        if (patronId === "serieA_igual_cadena_oficial") return "Serie A coincide celda a celda con la cadena circular oficial";
        if (patronId === "serieB_igual_cadena_oficial") return "Serie B coincide celda a celda con la cadena circular oficial";
        if (String(patronId).indexOf("mod10_e_vs_s_") === 0) {
          return "Perfil mod10(ei − si) = " + String(patronId).replace("mod10_e_vs_s_", "");
        }
        return String(patronId);
      }

      function acorCategoriaFrecuenciaObservada(pct) {
        if (pct > 80) return "confirmados_estadisticamente";
        if (pct > 60) return "frecuentes";
        if (pct > 50) return "debiles";
        return "aislados";
      }

      function acorEtiquetaCategoriaDominante(cat) {
        if (cat === "confirmados_estadisticamente") return "Confirmados (frec. obs. >80%)";
        if (cat === "frecuentes") return "Frecuentes (frec. obs. >60%)";
        if (cat === "debiles") return "Débiles (frec. obs. >50%)";
        if (cat === "aislados") return "Aislados (frec. obs. ≤50%)";
        return String(cat || "");
      }

      function acorTextoFrecuenciaObservada(relacion, cantidad, n) {
        const p = n ? (100 * cantidad) / n : 0;
        return (
          "«" +
          relacion +
          "» aparece en " +
          p.toFixed(1) +
          "% de registros (" +
          cantidad +
          "/" +
          n +
          ")."
        );
      }

      function acorBuildPatronesDominantes(patrones, n) {
        const nota =
          "Clasificación por umbrales de frecuencia observada en el dataset cargado. No son reglas ni validez causal; solo conteos.";
        const porUmbral = { mas_del_50: [], mas_del_60: [], mas_del_70: [], mas_del_80: [] };
        const porCategoria = {
          confirmados_estadisticamente: [],
          frecuentes: [],
          debiles: [],
          aislados: []
        };
        const detalle = patrones.map(function (p) {
          const cant = p.cantidad;
          const pct = n ? (100 * cant) / n : 0;
          const desc = acorPatronDescripcionLegible(p.patron);
          const umb = {
            mas_del_50: pct > 50,
            mas_del_60: pct > 60,
            mas_del_70: pct > 70,
            mas_del_80: pct > 80
          };
          const cat = acorCategoriaFrecuenciaObservada(pct);
          const item = {
            patron_id: p.patron,
            relacion_observada: desc,
            cantidad: cant,
            total_registros: n,
            frecuencia_observada_pct: Number(pct.toFixed(4)),
            umbrales_mas_de: umb,
            categoria_frecuencia_observada: cat,
            texto_frecuencia_observada: acorTextoFrecuenciaObservada(desc, cant, n),
            registros: p.registros
          };
          if (umb.mas_del_50) porUmbral.mas_del_50.push(p.patron);
          if (umb.mas_del_60) porUmbral.mas_del_60.push(p.patron);
          if (umb.mas_del_70) porUmbral.mas_del_70.push(p.patron);
          if (umb.mas_del_80) porUmbral.mas_del_80.push(p.patron);
          porCategoria[cat].push(item);
          return item;
        });
        return {
          nota: nota,
          total_registros_analizados: n,
          por_umbral_patron_id: porUmbral,
          por_categoria: porCategoria,
          detalle_todos_patrones: detalle
        };
      }

      function acorRelacionesCruzadasEnRegistro(rec, row, env) {
        const rels = [];
        const s = env.sDig;
        const e = env.eDig;
        const abA = env.abA;
        const abB = env.abB;
        if (abA && abB && s && e) {
          const An = abA[0] * 10 + abA[1];
          const Bn = abB[0] * 10 + abB[1];
          if (An - Bn === 22 || Bn - An === 22) rels.push("A_num − B_num = ±22");
          if (Bn === An - 22) rels.push("B_num = A_num − 22");
          if (Bn === An + 22) rels.push("B_num = A_num + 22");
          if (abA[0] === espejoMap[e[1]]) rels.push("a1 = espejo(e2)");
          if (abA[1] === espejoMap[e[2]]) rels.push("a2 = espejo(e3)");
          if ((e[0] + e[1]) % 10 === abA[0]) rels.push("(e1 + e2) mod 10 = a1");
          if ((e[0] + e[1] + e[2]) % 10 === abA[0]) rels.push("(e1 + e2 + e3) mod 10 = a1");
        }
        if (s && s[0] === s[3]) rels.push("s1 = s4");
        if (e && s && e[0] === s[3]) rels.push("e1 = s4");
        if (acorSerieCircularCoincide(rec, env, "A")) rels.push("A circular coincidente con cadena oficial (serieA)");
        if (acorSerieCircularCoincide(rec, env, "B")) rels.push("B circular coincidente con cadena oficial (serieB)");
        return rels;
      }

      function acorAggregateRelacionesCruzadas(rows, registros) {
        const map = {};
        rows.forEach(function (row, idx) {
          const env = acorBuildEnv(registros[idx]);
          acorRelacionesCruzadasEnRegistro(registros[idx], row, env).forEach(function (rel) {
            if (!map[rel]) map[rel] = { relacion: rel, indices: [], count: 0 };
            map[rel].count++;
            map[rel].indices.push(row.indice);
          });
        });
        const n = rows.length || 1;
        return Object.keys(map)
          .map(function (k) {
            const o = map[k];
            return {
              relacion: o.relacion,
              frecuencia: o.count,
              frecuencia_observada_pct: Number(((100 * o.count) / n).toFixed(4)),
              registros: o.indices
            };
          })
          .sort(function (a, b) {
            return b.frecuencia - a.frecuencia;
          });
      }

      function acorAggregatePatterns(rows, registros) {
        const map = {};
        rows.forEach(function (row, idx) {
          const env = acorBuildEnv(registros[idx]);
          const tags = acorPatternTags(row, env);
          tags.forEach(function (t) {
            if (!map[t]) {
              map[t] = { patron: t, indices: [], count: 0 };
            }
            map[t].count++;
            map[t].indices.push(row.indice);
          });
        });
        const n = rows.length || 1;
        return Object.keys(map)
          .map(function (k) {
            const o = map[k];
            return {
              patron: o.patron,
              cantidad: o.count,
              porcentaje: ((100 * o.count) / n).toFixed(2) + "%",
              registros: o.indices
            };
          })
          .sort(function (a, b) {
            return b.cantidad - a.cantidad;
          });
      }

      function acorHeatText(freqMap) {
        const keys = Object.keys(freqMap).sort();
        let max = 1;
        keys.forEach(function (k) {
          if (freqMap[k] > max) max = freqMap[k];
        });
        return keys
          .map(function (k) {
            const v = freqMap[k];
            const inten = Math.round(40 + (120 * v) / max);
            return (
              '<span style="display:inline-block;margin:3px;padding:4px 8px;border-radius:6px;background:rgba(0,229,255,' +
              (inten / 255).toFixed(2) +
              ')">' +
              escapeHtml(k + ":" + v) +
              "</span>"
            );
          })
          .join(" ");
      }

      function acorBuildHypoResDetailed(text, regs) {
        if (!text || !String(text).trim()) return null;
        const t = String(text);
        let hits = 0;
        let evaluables = 0;
        const fallosDet = [];
        const okIdx = [];
        const failIdx = [];
        regs.forEach(function (rec, i) {
          const m = acorHypothesisMatchRecord(t, rec);
          if (m.evaluable && m.acierto !== null) {
            evaluables++;
            if (m.acierto) {
              hits++;
              okIdx.push(i + 1);
            } else {
              failIdx.push(i + 1);
              if (fallosDet.length < 25) {
                fallosDet.push({ indice: i + 1, semilla: sanitize4(rec.semilla), detalle: m });
              }
            }
          }
        });
        const pctNum = evaluables ? (100 * hits) / evaluables : null;
        return {
          texto_hipotesis: t,
          casos_evaluables: evaluables,
          aciertos: hits,
          fallos: evaluables - hits,
          porcentaje: pctNum !== null ? pctNum.toFixed(2) + "%" : "n/d",
          porcentaje_num: pctNum,
          registros_acertados: okIdx,
          registros_fallados: failIdx,
          fallos_muestra: fallosDet
        };
      }

      function acorRankingHipotesisDesdeCola(regs) {
        if (!acorHipotesisColaExperimental.length) return [];
        const arr = acorHipotesisColaExperimental.map(function (h, i) {
          const r = acorBuildHypoResDetailed(h, regs);
          return r ? Object.assign({ orden_cola: i + 1 }, r) : null;
        }).filter(Boolean);
        arr.sort(function (a, b) {
          const pa = a.porcentaje_num != null ? a.porcentaje_num : -1;
          const pb = b.porcentaje_num != null ? b.porcentaje_num : -1;
          if (pb !== pa) return pb - pa;
          return (b.aciertos || 0) - (a.aciertos || 0);
        });
        return arr;
      }

      function acorEnvDiscoveryFromRec(rec) {
        const sDig = acorDigitsFromSeed4(rec.semilla);
        const eDig = acorDigitsFromEq3(rec.equivalente);
        const abA = acorPairFromInicio(rec.inicioA);
        const abB = acorPairFromInicio(rec.inicioB);
        if (!sDig || !eDig || !abA || !abB) return null;
        return {
          s1: sDig[0],
          s2: sDig[1],
          s3: sDig[2],
          s4: sDig[3],
          e1: eDig[0],
          e2: eDig[1],
          e3: eDig[2],
          a1: abA[0],
          a2: abA[1],
          b1: abB[0],
          b2: abB[1],
          A_num: abA[0] * 10 + abA[1],
          B_num: abB[0] * 10 + abB[1]
        };
      }

      function acorBuscarCoincidencias(textoRaw, regs) {
        const raw = String(textoRaw || "").trim().replace(/\u2212/g, "-");
        if (!raw) {
          return { error: "Vacío", modulo: "MODO_ANALISIS_CORRELACIONAL_AB" };
        }
        const nota =
          "Solo medición de coincidencias en el dataset cargado. Sin interpretación automática ni conclusiones.";
        const comparadores = ["===", "==", ">=", "<=", "!=", "<", ">"];
        let op = null;
        let idxOp = -1;
        comparadores.forEach(function (c) {
          const j = raw.indexOf(c);
          if (j >= 0 && (idxOp < 0 || j < idxOp)) {
            idxOp = j;
            op = c;
          }
        });
        if (op && idxOp >= 0) {
          const lhs = raw.slice(0, idxOp).trim();
          const rhs = raw.slice(idxOp + op.length).trim();
          const okReg = [];
          const badReg = [];
          let noEval = 0;
          regs.forEach(function (rec, i) {
            const env = acorEnvDiscoveryFromRec(rec);
            if (!env) {
              noEval++;
              return;
            }
            try {
              const vl = acorEvalDiscoveryExpr(lhs, env);
              const vr = acorEvalDiscoveryExpr(rhs, env);
              const nl = Number(vl);
              const nr = Number(vr);
              const okn = Number.isFinite(nl) && Number.isFinite(nr);
              let hit = false;
              if (op === "===" || op === "==") {
                hit = okn ? Math.round(nl) === Math.round(nr) : String(vl) === String(vr);
              } else if (op === ">=") hit = okn && nl >= nr;
              else if (op === "<=") hit = okn && nl <= nr;
              else if (op === "!=") hit = okn ? Math.round(nl) !== Math.round(nr) : String(vl) !== String(vr);
              else if (op === ">") hit = okn && nl > nr;
              else if (op === "<") hit = okn && nl < nr;
              if (hit) okReg.push(i + 1);
              else badReg.push(i + 1);
            } catch (err) {
              noEval++;
              badReg.push(i + 1);
            }
          });
          return {
            modulo: "MODO_ANALISIS_CORRELACIONAL_AB",
            nota: nota,
            entrada: raw,
            modo: "relacion_booleana",
            operador: op,
            veces_verdadero: okReg.length,
            registros_verdadero: okReg,
            registros_falso: badReg,
            registros_sin_evaluar_por_datos: noEval
          };
        }
        const hist = {};
        let sinDatos = 0;
        regs.forEach(function (rec, i) {
          const env = acorEnvDiscoveryFromRec(rec);
          if (!env) {
            sinDatos++;
            return;
          }
          try {
            const v = acorEvalDiscoveryExpr(raw, env);
            const k = String(Math.round(Number(v)));
            if (!hist[k]) hist[k] = [];
            hist[k].push(i + 1);
          } catch (err) {
            sinDatos++;
          }
        });
        const distribucion = Object.keys(hist)
          .map(function (k) {
            return { valor_resultado: k, veces: hist[k].length, registros: hist[k] };
          })
          .sort(function (a, b) {
            return b.veces - a.veces;
          });
        return {
          modulo: "MODO_ANALISIS_CORRELACIONAL_AB",
          nota: nota,
          entrada: raw,
          modo: "distribucion_valor_expresion",
          total_registros: regs.length,
          registros_sin_evaluar_por_datos_o_error: sinDatos,
          distribucion_por_valor_redondeado: distribucion
        };
      }

      function acorRenderExtensionesCorrel(rows, patronesDominantes, relaciones, ranking, busqueda) {
        const domBody = document.getElementById("acorDominantesBody");
        if (domBody && patronesDominantes) {
          const d = patronesDominantes.detalle_todos_patrones || [];
          const destacados = d.filter(function (x) {
            return x.frecuencia_observada_pct > 50;
          });
          if (!destacados.length) {
            domBody.innerHTML =
              '<tr><td colspan="6" class="acor-muted">Ningún patrón supera el 50% en este dataset (véase JSON «patrones_dominantes» para desglose completo).</td></tr>';
          } else {
            domBody.innerHTML = destacados
              .map(function (x) {
                return (
                  "<tr><td>" +
                  escapeHtml(acorEtiquetaCategoriaDominante(x.categoria_frecuencia_observada)) +
                  "</td><td>" +
                escapeHtml(x.relacion_observada) +
                "</td><td>" +
                x.cantidad +
                "</td><td>" +
                x.frecuencia_observada_pct.toFixed(2) +
                "%</td><td>" +
                escapeHtml(x.texto_frecuencia_observada) +
                "</td><td>" +
                escapeHtml(x.registros.join(", ")) +
                "</td></tr>"
                );
              })
              .join("");
          }
        }
        const rxBody = document.getElementById("acorRelacionesCruzadasBody");
        if (rxBody && relaciones) {
          rxBody.innerHTML = relaciones
            .map(function (r) {
              return (
                "<tr><td>" +
                escapeHtml(r.relacion) +
                "</td><td>" +
                r.frecuencia +
                "</td><td>" +
                r.frecuencia_observada_pct.toFixed(2) +
                "%</td><td>" +
                escapeHtml(r.registros.join(", ")) +
                "</td></tr>"
              );
            })
            .join("");
        }
        const rk = document.getElementById("acorRankingHipotesisBody");
        if (rk) {
          rk.innerHTML = (ranking || [])
            .map(function (h, rank) {
              return (
                "<tr><td>" +
                (rank + 1) +
                "</td><td><pre class=\"acor-pre\" style=\"margin:0;max-height:120px;overflow:auto\">" +
                escapeHtml(h.texto_hipotesis) +
                "</pre></td><td>" +
                h.aciertos +
                "</td><td>" +
                h.fallos +
                "</td><td>" +
                escapeHtml(h.porcentaje) +
                "</td><td>" +
                escapeHtml((h.registros_acertados || []).join(", ")) +
                "</td><td>" +
                escapeHtml((h.registros_fallados || []).join(", ")) +
                "</td></tr>"
              );
            })
            .join("");
        }
        const bq = document.getElementById("acorBusquedaResultado");
        if (bq) {
          bq.innerHTML = busqueda
            ? "<pre class=\"acor-pre\" style=\"max-height:260px\">" + escapeHtml(JSON.stringify(busqueda, null, 2)) + "</pre>"
            : '<p class="acor-muted">(sin búsqueda en esta sesión)</p>';
        }
        const colaEl = document.getElementById("acorColaHipotesisResumen");
        if (colaEl) {
          colaEl.textContent = acorHipotesisColaExperimental.length
            ? acorHipotesisColaExperimental.length + " hipótesis en cola experimental (solo memoria de sesión)."
            : "Cola vacía.";
        }
      }

      function acorRenderOverlay(pack, rows, patrones, freqOps, hypoRes) {
        const sum = document.getElementById("acorSummaryMount");
        if (sum) {
          sum.innerHTML =
            "<p>Registros: <strong>" +
            rows.length +
            "</strong> · Fuente: <code>historicos_maestro.json</code></p>" +
            "<p class=\"acor-muted\">Sin conclusiones automáticas. Herramientas bajo <code>MODO_ANALISIS_CORRELACIONAL_AB</code>: solo frecuencias observadas y contrastes explícitos.</p>";
        }
        const tb = document.getElementById("acorPatronesBody");
        if (tb) {
          tb.innerHTML = patrones
            .map(function (p) {
              return (
                "<tr><td>" +
                escapeHtml(p.patron) +
                "</td><td>" +
                p.cantidad +
                "</td><td>" +
                escapeHtml(p.porcentaje) +
                "</td><td>" +
                escapeHtml(p.registros.join(", ")) +
                "</td></tr>"
              );
            })
            .join("");
        }
        const hx = document.getElementById("acorHeatmapMount");
        if (hx) {
          hx.innerHTML = acorHeatText(freqOps);
        }
        const mod = document.getElementById("acorResumenModular");
        if (mod) {
          const top = patrones.slice(0, 12);
          mod.innerHTML =
            "<ul style=\"margin:0;padding-left:18px\">" +
            top
              .map(function (p) {
                return "<li>" + escapeHtml(p.patron) + " — " + p.cantidad + " (" + escapeHtml(p.porcentaje) + ")</li>";
              })
              .join("") +
            "</ul>";
        }
        const cx = document.getElementById("acorCoincidenciasBody");
        if (cx) {
          const arr = Object.keys(freqOps)
            .map(function (k) {
              return { clave: k, n: freqOps[k] };
            })
            .sort(function (a, b) {
              return b.n - a.n;
            });
          cx.innerHTML = arr
            .map(function (r) {
              return (
                "<tr><td>" +
                escapeHtml(r.clave) +
                "</td><td>" +
                r.n +
                "</td><td>" +
                escapeHtml(((100 * r.n) / (rows.length || 1)).toFixed(1) + "%") +
                "</td></tr>"
              );
            })
            .join("");
        }
        const det = document.getElementById("acorDetallePre");
        if (det) {
          det.textContent = JSON.stringify(rows, null, 2);
        }
        const hm = document.getElementById("acorHypoMsg");
        if (hm) {
          if (hypoRes) {
            hm.innerHTML =
              "<pre class=\"acor-pre\">" +
              escapeHtml(JSON.stringify(hypoRes, null, 2)) +
              "</pre>";
          } else {
            hm.innerHTML = '<p class="acor-muted">(sin ejecución de hipótesis en esta pasada; use el botón o exporte con texto en el área)</p>';
          }
        }
        acorRenderExtensionesCorrel(
          rows,
          acorLastPatronesDominantes,
          acorLastRelacionesCruzadas,
          acorLastRankingHipotesis,
          acorLastCoincidenciasBusqueda
        );
      }

      function acorFreqOpsFromRows(rows, registros) {
        const f = {};
        function bump(k) {
          f[k] = (f[k] || 0) + 1;
        }
        rows.forEach(function (row, idx) {
          const env = acorBuildEnv(registros[idx]);
          acorPatternTags(row, env).forEach(function (t) {
            bump("pat:" + t);
          });
          if (row.A_semilla_equiv && row.A_semilla_equiv.diferencias_mod10_e_s) {
            row.A_semilla_equiv.diferencias_mod10_e_s.forEach(function (m, j) {
              bump("e" + (j + 1) + "s" + (j + 1) + "_m" + m);
            });
          }
        });
        return f;
      }

      function acorBuildHypoRes(hypoText, regs) {
        const d = acorBuildHypoResDetailed(hypoText, regs);
        if (!d) return null;
        return {
          texto_hipotesis: d.texto_hipotesis,
          casos_evaluables: d.casos_evaluables,
          aciertos: d.aciertos,
          fallos_muestra: d.fallos_muestra,
          porcentaje:
            d.casos_evaluables ? d.porcentaje + " sobre casos con A/B y semilla+equiv completos" : "n/d"
        };
      }

      function acorRunFull(hypoText) {
        return acorFetchMaestro().then(function (pack) {
          const regs = pack.registros || [];
          acorLastRegs = regs;
          acorLastCoincidenciasBusqueda = null;
          const rows = regs.map(function (r, i) {
            return acorAnalyzeRecord(r, i);
          });
          acorLastRows = rows;
          const patrones = acorAggregatePatterns(rows, regs);
          const freqOps = acorFreqOpsFromRows(rows, regs);
          const hypoRes = acorBuildHypoRes(hypoText, regs);
          acorLastHypothesisResult = hypoRes;
          acorLastPatronesDominantes = acorBuildPatronesDominantes(patrones, rows.length);
          acorLastRelacionesCruzadas = acorAggregateRelacionesCruzadas(rows, regs);
          acorLastRankingHipotesis = acorRankingHipotesisDesdeCola(regs);
          acorLastExport = {
            exportado: new Date().toISOString(),
            modulo: "MODO_ANALISIS_CORRELACIONAL_AB",
            app_version: APP_VERSION,
            dataset_original: pack.raw,
            metricas: rows,
            correlaciones: rows.map(function (r) {
              return { indice: r.indice, A: r.A_semilla_equiv, B: r.B_equiv_inicios, C: r.C_completo };
            }),
            frecuencias: freqOps,
            patrones: patrones,
            patrones_dominantes: acorLastPatronesDominantes,
            relaciones_cruzadas: acorLastRelacionesCruzadas,
            ranking_hipotesis: acorLastRankingHipotesis,
            coincidencias_busqueda: acorLastCoincidenciasBusqueda,
            hipotesis_ejecutadas: hypoRes ? [hypoRes] : [],
            firmas_repetidas: patrones.map(function (p) {
              return p.patron + "×" + p.cantidad;
            })
          };
          acorRenderOverlay(pack, rows, patrones, freqOps, hypoRes);
          const ov = document.getElementById("correlacionalOverlay");
          if (ov) {
            ov.style.display = "block";
            ov.setAttribute("aria-hidden", "false");
          }
        })
          .catch(function (err) {
            const sum = document.getElementById("acorSummaryMount");
            if (sum) {
              sum.innerHTML =
                '<p class="acor-muted">Error al cargar <code>historicos_maestro.json</code>: ' +
                escapeHtml(String(err && err.message ? err.message : err)) +
                "</p>";
            }
            [
              "acorPatronesBody",
              "acorHeatmapMount",
              "acorResumenModular",
              "acorCoincidenciasBody",
              "acorHypoMsg",
              "acorDominantesBody",
              "acorRelacionesCruzadasBody",
              "acorRankingHipotesisBody",
              "acorBusquedaResultado"
            ].forEach(function (id) {
              const n = document.getElementById(id);
              if (n) n.innerHTML = "";
            });
            const pre = document.getElementById("acorDetallePre");
            if (pre) pre.textContent = "";
            const ovErr = document.getElementById("correlacionalOverlay");
            if (ovErr) {
              ovErr.style.display = "block";
              ovErr.setAttribute("aria-hidden", "false");
            }
          });
      }

      function setupModoAnalisisCorrelacionalAB() {
        const btn = document.getElementById("btnAnalisisCorrelacional");
        const ov = document.getElementById("correlacionalOverlay");
        const btnClose = document.getElementById("btnCerrarCorrelacional");
        const btnReload = document.getElementById("btnRecargarCorrelacional");
        const btnEx = document.getElementById("btnExportarCorrelacional");
        const btnHypo = document.getElementById("btnEjecutarHipotesisCorrel");
        const taHypo = document.getElementById("acorHipotesisTextarea");
        const btnColaAdd = document.getElementById("btnAcorColaAdd");
        const btnColaClear = document.getElementById("btnAcorColaClear");
        const btnColaRun = document.getElementById("btnAcorColaRun");
        const btnBuscar = document.getElementById("btnAcorBuscarCoincidencias");
        const inpBusq = document.getElementById("acorBusquedaCoincidenciasInput");
        if (!btn || !ov) return;
        btn.addEventListener("click", function () {
          acorRunFull("");
        });
        if (btnReload) {
          btnReload.addEventListener("click", function () {
            acorRunFull("");
          });
        }
        if (btnClose) {
          btnClose.addEventListener("click", function () {
            ov.style.display = "none";
            ov.setAttribute("aria-hidden", "true");
          });
        }
        ov.addEventListener("click", function (ev) {
          if (ev.target === ov) {
            ov.style.display = "none";
            ov.setAttribute("aria-hidden", "true");
          }
        });
        if (btnHypo && taHypo) {
          btnHypo.addEventListener("click", function () {
            acorRunFull(taHypo.value || "");
          });
        }
        if (btnColaAdd && taHypo) {
          btnColaAdd.addEventListener("click", function () {
            const t = String(taHypo.value || "").trim();
            if (!t) return;
            acorHipotesisColaExperimental.push(t);
            acorRenderExtensionesCorrel(
              acorLastRows || [],
              acorLastPatronesDominantes,
              acorLastRelacionesCruzadas,
              acorLastRankingHipotesis,
              acorLastCoincidenciasBusqueda
            );
          });
        }
        if (btnColaClear) {
          btnColaClear.addEventListener("click", function () {
            acorHipotesisColaExperimental = [];
            acorLastRankingHipotesis = [];
            acorRenderExtensionesCorrel(
              acorLastRows || [],
              acorLastPatronesDominantes,
              acorLastRelacionesCruzadas,
              acorLastRankingHipotesis,
              acorLastCoincidenciasBusqueda
            );
            if (acorLastExport) acorLastExport.ranking_hipotesis = [];
          });
        }
        if (btnColaRun && taHypo) {
          btnColaRun.addEventListener("click", function () {
            if (!acorLastRegs) {
              window.alert("Ejecute primero «Análisis correlacional» para cargar registros.");
              return;
            }
            acorLastRankingHipotesis = acorRankingHipotesisDesdeCola(acorLastRegs);
            if (acorLastExport) acorLastExport.ranking_hipotesis = acorLastRankingHipotesis;
            acorRenderExtensionesCorrel(
              acorLastRows || [],
              acorLastPatronesDominantes,
              acorLastRelacionesCruzadas,
              acorLastRankingHipotesis,
              acorLastCoincidenciasBusqueda
            );
          });
        }
        if (btnBuscar && inpBusq) {
          btnBuscar.addEventListener("click", function () {
            if (!acorLastRegs) {
              window.alert("Ejecute primero «Análisis correlacional» para cargar registros.");
              return;
            }
            acorLastCoincidenciasBusqueda = acorBuscarCoincidencias(inpBusq.value || "", acorLastRegs);
            if (acorLastExport) acorLastExport.coincidencias_busqueda = acorLastCoincidenciasBusqueda;
            acorRenderExtensionesCorrel(
              acorLastRows || [],
              acorLastPatronesDominantes,
              acorLastRelacionesCruzadas,
              acorLastRankingHipotesis,
              acorLastCoincidenciasBusqueda
            );
          });
        }
        if (btnEx) {
          btnEx.addEventListener("click", function () {
            if (!acorLastExport) {
              window.alert("Ejecute primero el análisis correlacional o la hipótesis.");
              return;
            }
            const raw = acorLastExport.dataset_original;
            const regs =
              raw && Array.isArray(raw.registros)
                ? raw.registros
                : Array.isArray(raw)
                  ? raw
                  : [];
            const ht = taHypo && taHypo.value.trim();
            if (ht) {
              acorLastExport.hipotesis_ejecutadas = [acorBuildHypoRes(ht, regs)].filter(Boolean);
            }
            acorLastExport.patrones_dominantes = acorLastPatronesDominantes;
            acorLastExport.relaciones_cruzadas = acorLastRelacionesCruzadas;
            acorLastExport.ranking_hipotesis = acorLastRankingHipotesis || [];
            acorLastExport.coincidencias_busqueda = acorLastCoincidenciasBusqueda;
            const blob = new Blob([JSON.stringify(acorLastExport, null, 2)], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "analisis_correlacional_ab.json";
            a.click();
            URL.revokeObjectURL(url);
          });
        }
      }

      setupModoAnalisisCorrelacionalAB();
      /* /MODO_ANALISIS_CORRELACIONAL_AB */
