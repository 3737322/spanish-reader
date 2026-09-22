# -*- coding: utf-8 -*-
"""
Genera data/lex_irregular.json : lexico de formas verbales (lematizador).

Diseno:
  * Un motor de conjugacion regular con las reglas ortograficas del espanol
    (c->qu, g->gu, z->c, gu->gu-dieresis, g->j, c->z/zc, cambios de raiz, etc.).
  * Una tabla curada a mano con lo genuinamente irregular.
  * Aserciones sobre ~700 formas criticas (sobre todo acentos) que se comprueban
    antes de escribir el fichero.

Convenios:
  * p = 1s/2s/3s/1p/2p/3p, "-" para ger./part.
  * Cuando 1s y 3s coinciden (imp., cond., subj.) se conserva una sola entrada
    etiquetada 3s (JSON no admite claves repetidas).
  * Si dos formas de verbos distintos coinciden (ve, ven, se, di, viste...),
    gana la etiqueta mas frecuente en texto (regla global pres.>pret.>imp.>fut.>cond.>subj.>imper.
    + EXCEPCIONES).
"""
import io
import json
import os
import sys

VOWELS = set("aeiouáéíóúü")
ACC = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
SC_WEAK = {"e": "i", "o": "u", "i": "i", "u": "u"}


# --------------------------------------------------------------------------
# motor
# --------------------------------------------------------------------------
def cls_of(inf):
    """Clase de conjugacion, normalizando infinitivos con tilde (oír, reír, freír)."""
    return {"ír": "ir", "ér": "er", "ár": "ar"}.get(inf[-2:], inf[-2:])


def apply_sc(stem, sc, weak=False):
    """Aplica el cambio de raiz al ultimo vocal de la raiz (e->ie, o->ue, e->i...)."""
    if not sc:
        return stem
    src, dst = sc
    d = SC_WEAK.get(src, src) if weak else dst
    i = stem.rfind(src)
    if i < 0:
        return stem
    res = stem[:i] + d + stem[i + 1:]
    # dieresis: g + ue/ui -> güe/güi  (avergonzar -> avergüenzo)
    if d.startswith("u") and i > 0 and res[i - 1] == "g" and i + 1 < len(res) and res[i + 1] in "ei":
        res = res[:i] + "ü" + res[i + 1:]
    return res


def accent_last_vowel(s):
    for i in range(len(s) - 1, -1, -1):
        if s[i] in VOWELS:
            return s[:i] + ACC.get(s[i], s[i]) + s[i + 1:]
    return s


def ar_pret_1s(stem):
    """1a sg del pretérito de los verbos en -ar (busqué, llegué, empecé, averigüé)."""
    if stem.endswith("gu"):
        return stem[:-1] + "üé"
    if stem.endswith("c"):
        return stem[:-1] + "qué"
    if stem.endswith("g"):
        return stem[:-1] + "gué"
    if stem.endswith("z"):
        return stem[:-1] + "cé"
    return stem + "é"


def ar_subj_stem(stem):
    """Raiz del subjuntivo de los verbos en -ar (busque, llegue, empiece, averigüe)."""
    if stem.endswith("gu"):
        return stem[:-1] + "ü"
    if stem.endswith("c"):
        return stem[:-1] + "qu"
    if stem.endswith("g"):
        return stem[:-1] + "gu"
    if stem.endswith("z"):
        return stem[:-1] + "c"
    return stem


def erir_pres1s(s):
    """1a sg del presente de -er/-ir: coger->cojo, seguir->sigo, vencer->venzo."""
    if s.endswith("gu"):
        return s[:-1] + "o"
    if s.endswith("g"):
        return s[:-1] + "jo"
    if s.endswith("c"):
        return s[:-1] + "zo"
    return s + "o"


END_PRES = {"ar": ["o", "as", "a", "amos", "áis", "an"],
            "er": ["o", "es", "e", "emos", "éis", "en"],
            "ir": ["o", "es", "e", "imos", "ís", "en"]}
END_SUBJ = {"ar": ["e", "es", "e", "emos", "éis", "en"],
            "er": ["a", "as", "a", "amos", "áis", "an"],
            "ir": ["a", "as", "a", "amos", "áis", "an"]}
END_IMP = {"ar": ["aba", "abas", "aba", "ábamos", "abais", "aban"],
           "er": ["ía", "ías", "ía", "íamos", "íais", "ían"],
           "ir": ["ía", "ías", "ía", "íamos", "íais", "ían"]}
END_FUT = ["é", "ás", "á", "emos", "éis", "án"]
END_COND = ["ía", "ías", "ía", "íamos", "íais", "ían"]


def pres_forms(v):
    if v.get("pres"):
        return list(v["pres"])
    inf, stem, cls = v["inf"], v["inf"][:-2], cls_of(v["inf"])
    sc, h = v.get("sc"), v.get("h_asp")
    out = []
    for i, e in enumerate(END_PRES[cls]):
        s = stem
        if sc and i in (0, 1, 2, 5):
            s = apply_sc(stem, sc)
            if h and s[:2] in ("ue", "ie"):
                s = "h" + s
        if i == 0:
            if v.get("pres1s"):
                out.append(v["pres1s"])
                continue
            if cls in ("er", "ir"):
                out.append(erir_pres1s(s))
                continue
        if v.get("diph") and i in (0, 1, 2, 5):
            s = accent_last_vowel(s)
        out.append(s + e)
    return out


def pret_forms(v):
    if v.get("pret"):
        return list(v["pret"])
    stem, cls = v["inf"][:-2], cls_of(v["inf"])
    if cls == "ar":
        return [ar_pret_1s(stem), stem + "aste", stem + "ó",
                stem + "amos", stem + "asteis", stem + "aron"]
    sc = v.get("sc")
    s3 = apply_sc(stem, sc, weak=True) if (sc and cls == "ir") else stem
    return [stem + "í", stem + "iste", s3 + "ió",
            stem + "imos", stem + "isteis", s3 + "ieron"]


def imp_forms(v):
    if v.get("imp"):
        return list(v["imp"])
    stem, cls = v["inf"][:-2], cls_of(v["inf"])
    return [stem + e for e in END_IMP[cls]]


def fut_base(v):
    """Raiz de futuro/condicional: el infinitivo, pero oír->oir-, reír->reir-."""
    base = v.get("fut_stem") or v["inf"]
    if base.endswith("ír"):
        base = base[:-2] + "ir"
    return base


def fut_forms(v):
    if v.get("fut"):
        return list(v["fut"])
    return [fut_base(v) + e for e in END_FUT]


def cond_forms(v):
    if v.get("cond"):
        return list(v["cond"])
    return [fut_base(v) + e for e in END_COND]


def subj_forms(v):
    if v.get("subj"):
        return list(v["subj"])
    inf, stem, cls = v["inf"], v["inf"][:-2], cls_of(v["inf"])
    sc = v.get("sc")
    if v.get("only3s"):
        s = apply_sc(stem, sc) if sc else stem
        if v.get("h_asp") and s[:2] in ("ue", "ie"):
            s = "h" + s
        return [None, None, s + END_SUBJ[cls][2], None, None, None]
    pres1s = v.get("pres1s") or (v["pres"][0] if v.get("pres") else pres_forms(v)[0])
    # base acentuada (1s/2s/3s/3p): sale del presente de indicativo 1s
    if cls == "ar":
        base_st = ar_subj_stem(pres1s[:-1])
        base_un = ar_subj_stem(stem)
    else:
        base_st = pres1s[:-1]
        if sc and cls == "ir":
            base_un = apply_sc(stem, sc, weak=True)
            if stem.endswith("gu"):        # seguir, conseguir -> sigamos
                base_un = base_un[:-1]
            elif stem.endswith("g"):       # elegir, corregir, regir -> elijamos
                base_un = base_un[:-1] + "j"
        elif sc:
            base_un = stem
        else:
            base_un = pres1s[:-1]          # ya trae la ortografia de la 1s (coj-, conozc-)
    out = []
    for i, e in enumerate(END_SUBJ[cls]):
        out.append((base_st if i in (0, 1, 2, 5) else base_un) + e)
    return out


def ger_form(v):
    if v.get("ger"):
        return v["ger"]
    stem, cls = v["inf"][:-2], cls_of(v["inf"])
    if cls == "ar":
        return stem + "ando"
    s = stem
    if v.get("sc"):
        s = apply_sc(stem, v["sc"], weak=True)
    if v.get("h_asp") and s[:2] in ("ue", "ie"):
        s = "h" + s
    return s + "iendo"


def part_form(v):
    if v.get("part"):
        return v["part"]
    stem, cls = v["inf"][:-2], cls_of(v["inf"])
    return stem + ("ado" if cls == "ar" else "ido")


def imper_forms(v):
    """Devuelve (2s, 2p) o None si el verbo carece de imperativo."""
    if v.get("no_imper"):
        return None
    cls = cls_of(v["inf"])
    p2s = v.get("imper2s") or pres_forms(v)[2]
    if v.get("imper2p"):
        p2p = v["imper2p"]
    elif v["inf"].endswith("ír"):          # oír -> oíd, reír -> reíd, freír -> freíd
        p2p = v["inf"][:-2] + "íd"
    else:
        p2p = v["inf"][:-2] + {"ar": "ad", "er": "ed", "ir": "id"}[cls]
    return p2s, p2p


# --------------------------------------------------------------------------
# tabla de verbos
# --------------------------------------------------------------------------
def V(inf, **kw):
    kw["inf"] = inf
    return kw


VERBS = [
    # ---- ser / estar / haber / tener / hacer ----
    V("ser", pres=["soy", "eres", "es", "somos", "sois", "son"],
      pret=["fui", "fuiste", "fue", "fuimos", "fuisteis", "fueron"],
      imp=["era", "eras", "era", "éramos", "erais", "eran"],
      subj=["sea", "seas", "sea", "seamos", "seáis", "sean"],
      imper2s="sé", ger="siendo", part="sido"),
    V("estar", pres=["estoy", "estás", "está", "estamos", "estáis", "están"],
      pret=["estuve", "estuviste", "estuvo", "estuvimos", "estuvisteis", "estuvieron"],
      subj=["esté", "estés", "esté", "estemos", "estéis", "estén"],
      imper2s="está", ger="estando", part="estado"),
    V("haber", pres=["he", "has", "ha", "hemos", "habéis", "han"],
      pret=["hube", "hubiste", "hubo", "hubimos", "hubisteis", "hubieron"],
      fut_stem="habr", subj=["haya", "hayas", "haya", "hayamos", "hayáis", "hayan"],
      no_imper=True, ger="habiendo", part="habido",
      extra=[("hay", "pres.", "3s")]),
    V("tener", pres=["tengo", "tienes", "tiene", "tenemos", "tenéis", "tienen"],
      pret=["tuve", "tuviste", "tuvo", "tuvimos", "tuvisteis", "tuvieron"],
      fut_stem="tendr", imper2s="ten", ger="teniendo", part="tenido"),
    V("hacer", pres=["hago", "haces", "hace", "hacemos", "hacéis", "hacen"],
      pret=["hice", "hiciste", "hizo", "hicimos", "hicisteis", "hicieron"],
      fut_stem="har", imper2s="haz", ger="haciendo", part="hecho"),
    # ---- ir / venir / poder / decir / ver / dar / saber / querer / poner / traer / salir ----
    V("ir", pres=["voy", "vas", "va", "vamos", "vais", "van"],
      pret=["fui", "fuiste", "fue", "fuimos", "fuisteis", "fueron"],
      imp=["iba", "ibas", "iba", "íbamos", "ibais", "iban"],
      subj=["vaya", "vayas", "vaya", "vayamos", "vayáis", "vayan"],
      imper2s="ve", ger="yendo", part="ido"),
    V("venir", pres=["vengo", "vienes", "viene", "venimos", "venís", "vienen"],
      pret=["vine", "viniste", "vino", "vinimos", "vinisteis", "vinieron"],
      fut_stem="vendr", imper2s="ven", ger="viniendo", part="venido"),
    V("poder", pres=["puedo", "puedes", "puede", "podemos", "podéis", "pueden"],
      pret=["pude", "pudiste", "pudo", "pudimos", "pudisteis", "pudieron"],
      fut_stem="podr", subj=["pueda", "puedas", "pueda", "podamos", "podáis", "puedan"],
      no_imper=True, ger="pudiendo", part="podido"),
    V("decir", pres=["digo", "dices", "dice", "decimos", "decís", "dicen"],
      pret=["dije", "dijiste", "dijo", "dijimos", "dijisteis", "dijeron"],
      fut_stem="dir", imper2s="di", ger="diciendo", part="dicho"),
    V("ver", pres=["veo", "ves", "ve", "vemos", "veis", "ven"],
      pret=["vi", "viste", "vio", "vimos", "visteis", "vieron"],
      imp=["veía", "veías", "veía", "veíamos", "veíais", "veían"],
      subj=["vea", "veas", "vea", "veamos", "veáis", "vean"],
      imper2s="ve", ger="viendo", part="visto"),
    V("dar", pres=["doy", "das", "da", "damos", "dais", "dan"],
      pret=["di", "diste", "dio", "dimos", "disteis", "dieron"],
      subj=["dé", "des", "dé", "demos", "deis", "den"],
      imper2s="da", ger="dando", part="dado"),
    V("saber", pres=["sé", "sabes", "sabe", "sabemos", "sabéis", "saben"],
      pret=["supe", "supiste", "supo", "supimos", "supisteis", "supieron"],
      fut_stem="sabr", subj=["sepa", "sepas", "sepa", "sepamos", "sepáis", "sepan"],
      imper2s="sabe", ger="sabiendo", part="sabido"),
    V("querer", pres=["quiero", "quieres", "quiere", "queremos", "queréis", "quieren"],
      pret=["quise", "quisiste", "quiso", "quisimos", "quisisteis", "quisieron"],
      fut_stem="querr", subj=["quiera", "quieras", "quiera", "queramos", "queráis", "quieran"],
      imper2s="quiere", ger="queriendo", part="querido"),
    V("poner", pres=["pongo", "pones", "pone", "ponemos", "ponéis", "ponen"],
      pret=["puse", "pusiste", "puso", "pusimos", "pusisteis", "pusieron"],
      fut_stem="pondr", imper2s="pon", ger="poniendo", part="puesto"),
    V("traer", pres1s="traigo",
      pret=["traje", "trajiste", "trajo", "trajimos", "trajisteis", "trajeron"],
      imper2s="trae", ger="trayendo", part="traído"),
    V("salir", pres1s="salgo", fut_stem="saldr", imper2s="sal",
      ger="saliendo", part="salido"),
    # ---- e->i / e->ie / o->ue en -ir ----
    V("seguir", sc=("e", "i"), ger="siguiendo", part="seguido"),
    V("conseguir", sc=("e", "i"), ger="consiguiendo", part="conseguido"),
    V("sentir", sc=("e", "ie"), ger="sintiendo", part="sentido"),
    V("servir", sc=("e", "i"), ger="sirviendo", part="servido"),
    V("vestir", sc=("e", "i"), ger="vistiendo", part="vestido"),
    V("pedir", sc=("e", "i"), ger="pidiendo", part="pedido"),
    V("repetir", sc=("e", "i"), ger="repitiendo", part="repetido"),
    V("medir", sc=("e", "i"), ger="midiendo", part="medido"),
    V("dormir", sc=("o", "ue"), ger="durmiendo", part="dormido"),
    V("morir", sc=("o", "ue"), ger="muriendo", part="muerto"),
    V("preferir", sc=("e", "ie"), ger="prefiriendo", part="preferido"),
    V("mentir", sc=("e", "ie"), ger="mintiendo", part="mentido"),
    V("convertir", sc=("e", "ie"), ger="convirtiendo", part="convertido"),
    # ---- o->ue / e->ie en -ar y -er ----
    V("jugar", sc=("u", "ue"), ger="jugando", part="jugado"),
    V("pensar", sc=("e", "ie"), ger="pensando", part="pensado"),
    V("cerrar", sc=("e", "ie"), ger="cerrando", part="cerrado"),
    V("empezar", sc=("e", "ie"), ger="empezando", part="empezado"),
    V("comenzar", sc=("e", "ie"), ger="comenzando", part="comenzado"),
    V("entender", sc=("e", "ie"), ger="entendiendo", part="entendido"),
    V("perder", sc=("e", "ie"), ger="perdiendo", part="perdido"),
    V("volver", sc=("o", "ue"), ger="volviendo", part="vuelto"),
    V("volar", sc=("o", "ue"), ger="volando", part="volado"),
    V("contar", sc=("o", "ue"), ger="contando", part="contado"),
    V("encontrar", sc=("o", "ue"), ger="encontrando", part="encontrado"),
    V("recordar", sc=("o", "ue"), ger="recordando", part="recordado"),
    V("mostrar", sc=("o", "ue"), ger="mostrando", part="mostrado"),
    V("probar", sc=("o", "ue"), ger="probando", part="probado"),
    V("soñar", sc=("o", "ue"), ger="soñando", part="soñado"),
    V("mover", sc=("o", "ue"), ger="moviendo", part="movido"),
    V("resolver", sc=("o", "ue"), ger="resolviendo", part="resuelto"),
    V("devolver", sc=("o", "ue"), ger="devolviendo", part="devuelto"),
    V("envolver", sc=("o", "ue"), ger="envolviendo", part="envuelto"),
    V("almorzar", sc=("o", "ue"), ger="almorzando", part="almorzado"),
    V("tropezar", sc=("e", "ie"), ger="tropezando", part="tropezado"),
    V("llover", sc=("o", "ue"), only3s=True, no_imper=True, ger="lloviendo", part="llovido"),
    # ---- oler / valer / caber / caer / oir / huir / construir / incluir ----
    V("oler", sc=("o", "ue"), h_asp=True, ger="oliendo", part="olido"),
    V("valer", pres1s="valgo", fut_stem="valdr", imper2s="vale",
      ger="valiendo", part="valido"),
    V("caber", pres1s="quepo",
      pret=["cupe", "cupiste", "cupo", "cupimos", "cupisteis", "cupieron"],
      fut_stem="cabr", imper2s="cabe", ger="cabiendo", part="cabido"),
    V("caer", pres1s="caigo",
      pret=["caí", "caíste", "cayó", "caímos", "caísteis", "cayeron"],
      imper2s="cae", ger="cayendo", part="caído"),
    V("oír", pres=["oigo", "oyes", "oye", "oímos", "oís", "oyen"],
      pret=["oí", "oíste", "oyó", "oímos", "oísteis", "oyeron"],
      imper2s="oye", ger="oyendo", part="oído"),
    V("huir", pres=["huyo", "huyes", "huye", "huimos", "huís", "huyen"],
      pret=["huí", "huiste", "huyó", "huimos", "huisteis", "huyeron"],
      subj=["huya", "huyas", "huya", "huyamos", "huyáis", "huyan"],
      imper2s="huye", ger="huyendo", part="huido"),
    V("construir", pres=["construyo", "construyes", "construye", "construimos", "construís", "construyen"],
      pret=["construí", "construiste", "construyó", "construimos", "construisteis", "construyeron"],
      subj=["construya", "construyas", "construya", "construyamos", "construyáis", "construyan"],
      imper2s="construye", ger="construyendo", part="construido"),
    V("incluir", pres=["incluyo", "incluyes", "incluye", "incluimos", "incluís", "incluyen"],
      pret=["incluí", "incluiste", "incluyó", "incluimos", "incluisteis", "incluyeron"],
      subj=["incluya", "incluyas", "incluya", "incluyamos", "incluyáis", "incluyan"],
      imper2s="incluye", ger="incluyendo", part="incluido"),
    # ---- leer / creer / poseer / reir / sonreir ----
    V("leer", pret=["leí", "leíste", "leyó", "leímos", "leísteis", "leyeron"],
      subj=["lea", "leas", "lea", "leamos", "leáis", "lean"],
      ger="leyendo", part="leído"),
    V("creer", pret=["creí", "creíste", "creyó", "creímos", "creísteis", "creyeron"],
      subj=["crea", "creas", "crea", "creamos", "creáis", "crean"],
      ger="creyendo", part="creído"),
    V("poseer", pret=["poseí", "poseíste", "poseyó", "poseímos", "poseísteis", "poseyeron"],
      subj=["posea", "poseas", "posea", "poseamos", "poseáis", "posean"],
      ger="poseyendo", part="poseído"),
    V("reír", pres=["río", "ríes", "ríe", "reímos", "reís", "ríen"],
      pret=["reí", "reíste", "rió", "reímos", "reísteis", "rieron"],
      subj=["ría", "rías", "ría", "riamos", "riáis", "rían"],
      imper2s="ríe", ger="riendo", part="reído"),
    V("sonreír", pres=["sonrío", "sonríes", "sonríe", "sonreímos", "sonreís", "sonríen"],
      pret=["sonreí", "sonreíste", "sonrió", "sonreímos", "sonreísteis", "sonrieron"],
      subj=["sonría", "sonrías", "sonría", "sonriamos", "sonriáis", "sonrían"],
      imper2s="sonríe", ger="sonriendo", part="sonreído"),
    V("freír", pres=["frío", "fríes", "fríe", "freímos", "freís", "fríen"],
      pret=["freí", "freíste", "frió", "freímos", "freísteis", "frieron"],
      subj=["fría", "frías", "fría", "friamos", "friáis", "frían"],
      imper2s="fríe", ger="friendo", part="frito", extra_parts=["freído"]),
    # ---- -ucir / -cer / -cir ----
    V("producir", pres1s="produzco",
      pret=["produje", "produjiste", "produjo", "produjimos", "produjisteis", "produjeron"],
      ger="produciendo", part="producido"),
    V("traducir", pres1s="traduzco",
      pret=["traduje", "tradujiste", "tradujo", "tradujimos", "tradujisteis", "tradujeron"],
      ger="traduciendo", part="traducido"),
    V("conducir", pres1s="conduzco",
      pret=["conduje", "condujiste", "condujo", "condujimos", "condujisteis", "condujeron"],
      ger="conduciendo", part="conducido"),
    V("conocer", pres1s="conozco", ger="conociendo", part="conocido"),
    V("parecer", pres1s="parezco", ger="pareciendo", part="parecido"),
    V("agradecer", pres1s="agradezco", ger="agradeciendo", part="agradecido"),
    V("crecer", pres1s="crezco", ger="creciendo", part="crecido"),
    V("nacer", pres1s="nazco", ger="naciendo", part="nacido"),
    V("padecer", pres1s="padezco", ger="padeciendo", part="padecido"),
    V("ofrecer", pres1s="ofrezco", ger="ofreciendo", part="ofrecido"),
    V("permanecer", pres1s="permanezco", ger="permaneciendo", part="permanecido"),
    V("pertenecer", pres1s="pertenezco", ger="perteneciendo", part="pertenecido"),
    V("aparecer", pres1s="aparezco", ger="apareciendo", part="aparecido"),
    V("esparcir", pres1s="esparzo", ger="esparciendo", part="esparcido"),
    V("lucir", pres1s="luzco", ger="luciendo", part="lucido"),
    V("vencer", pres1s="venzo", ger="venciendo", part="vencido"),
    V("mecer", pres1s="mezo", ger="meciendo", part="mecido"),
    # ---- andar / satisfacer / bendecir / maldecir ----
    V("andar", pret=["anduve", "anduviste", "anduvo", "anduvimos", "anduvisteis", "anduvieron"],
      ger="andando", part="andado"),
    V("satisfacer", pres1s="satisfago",
      pret=["satisfice", "satisficiste", "satisfizo", "satisficimos", "satisficisteis", "satisficieron"],
      fut_stem="satisfar", imper2s="satisfaz", ger="satisfaciendo", part="satisfecho"),
    V("bendecir", pres=["bendigo", "bendices", "bendice", "bendecimos", "bendecís", "bendicen"],
      pret=["bendije", "bendijiste", "bendijo", "bendijimos", "bendijisteis", "bendijeron"],
      imper2s="bendice", ger="bendiciendo", part="bendito", extra_parts=["bendecido"]),
    V("maldecir", pres=["maldigo", "maldices", "maldice", "maldecimos", "maldecís", "maldicen"],
      pret=["maldije", "maldijiste", "maldijo", "maldijimos", "maldijisteis", "maldijeron"],
      imper2s="maldice", ger="maldiciendo", part="maldito", extra_parts=["maldecido"]),
    # ---- participios irregulares ----
    V("escribir", part="escrito"),
    V("describir", part="descrito"),
    V("abrir", part="abierto"),
    V("cubrir", part="cubierto"),
    V("romper", part="roto"),
    V("imprimir", part="impreso", extra_parts=["imprimido"]),
    # ---- -iar / -uar con acento en la raiz ----
    V("enviar", diph=True),
    V("confiar", diph=True),
    V("esquiar", diph=True),
    V("actuar", diph=True),
    V("continuar", diph=True),
    V("graduar", diph=True),
    V("situar", diph=True),
    V("averiguar"),
    V("avergonzar", sc=("o", "ue")),
    # ---- g->j / -ger / -gir / -guir ----
    V("coger"),
    V("recoger"),
    V("elegir", sc=("e", "i"), ger="eligiendo", part="elegido"),
    V("corregir", sc=("e", "i"), ger="corrigiendo", part="corregido"),
    V("regir", sc=("e", "i"), ger="rigiendo", part="regido"),
    V("dirigir"),
    V("exigir"),
    V("surgir"),
    V("urgir"),
    # ---- z->c / c->qu (regulares con cambio ortografico) ----
    V("cazar"), V("cruzar"), V("realizar"), V("analizar"), V("utilizar"),
    V("actualizar"), V("autorizar"), V("armonizar"),
    V("arrancar"), V("tocar"), V("buscar"), V("sacar"), V("explicar"),
    V("practicar"), V("aplicar"), V("dedicar"), V("indicar"), V("comunicar"),
    V("educar"), V("pescar"), V("aparcar"), V("acercar"), V("justificar"),
    V("identificar"), V("clasificar"), V("simplificar"), V("verificar"),
    V("certificar"),
    # ---- extra frecuentes ----
    V("acostar", sc=("o", "ue")),
    V("despertar", sc=("e", "ie")),
    V("divertir", sc=("e", "ie"), ger="divirtiendo", part="divertido"),
    V("adquirir", sc=("i", "ie"), ger="adquiriendo", part="adquirido"),
]

# orden de prioridad de tiempos para resolver colisiones de clave
TENSE_ORDER = ["part.", "ger.", "pres.", "pret.", "imp.", "fut.", "cond.", "subj.", "imper."]

VERB_ORDER = sorted([v["inf"] for v in VERBS])          # alfabetico: "ir" antes que "ser"
BY_INF = {v["inf"]: v for v in VERBS}

# colisiones entre verbos distintos resueltas a mano
EXCEPTIONS = {
    "di": ("decir", "imper.", "2s"),      # vs. dar pret. 1s
    "viste": ("ver", "pret.", "2s"),      # vs. vestir pres. 3s
}


def tense_table(v):
    """{tiempo: [forma,...]} con None en las casillas vacias."""
    t = {}
    pres = pres_forms(v)
    t["pres."] = pres
    t["pret."] = pret_forms(v)
    t["imp."] = imp_forms(v)
    t["fut."] = fut_forms(v)
    t["cond."] = cond_forms(v)
    t["subj."] = subj_forms(v)
    t["ger."] = [ger_form(v)]
    t["part."] = [part_form(v)]
    if v.get("only3s"):                       # verbos impersonales (llover)
        for k in ("pres.", "pret.", "imp.", "fut.", "cond.", "subj."):
            t[k] = [None, None, t[k][2], None, None, None]
    return t


def main():
    entries = {}
    for tense in TENSE_ORDER:
        for inf in VERB_ORDER:
            v = BY_INF[inf]
            if tense == "imper.":
                imp = imper_forms(v)
                if not imp:
                    continue
                pairs = [(imp[0], "2s"), (imp[1], "2p")]
                sub = subj_forms(v)
                for idx, per in ((2, "3s"), (5, "3p")):
                    if sub[idx]:
                        pairs.append((sub[idx], per))
            elif tense in ("ger.", "part."):
                pairs = [(tense_table(v)[tense][0], "-")]
            else:
                forms = tense_table(v)[tense]
                pairs = []
                last = {}
                for i, f in enumerate(forms):          # 1s y 3s identicos -> 3s
                    if f:
                        last[f] = i
                for i, f in enumerate(forms):
                    if f and last[f] == i:
                        pairs.append((f, ["1s", "2s", "3s", "1p", "2p", "3p"][i]))
            for f, per in pairs:
                if f not in entries:
                    entries[f] = (inf, tense, per)
    # participios alternativos y formas suplementarias
    for inf in VERB_ORDER:
        v = BY_INF[inf]
        for alt in v.get("extra_parts", []):
            entries.setdefault(alt, (inf, "part.", "-"))
        for f, t, p in v.get("extra", []):
            entries.setdefault(f, (inf, t, p))
    for f, (inf, t, p) in EXCEPTIONS.items():
        entries[f] = (inf, t, p)
    return entries


def write_json(entries, path):
    keys = sorted(entries)
    out = ["{"]
    for i, k in enumerate(keys):
        inf, t, p = entries[k]
        comma = "," if i < len(keys) - 1 else ""
        out.append('  %s: {"inf": "%s", "t": "%s", "p": "%s"}%s'
                   % (json.dumps(k, ensure_ascii=False), inf, t, p, comma))
    out.append("}")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


# --------------------------------------------------------------------------
# aserciones: (forma, infinitivo [, tiempo, persona])
# --------------------------------------------------------------------------
A2 = [
    ("tengo", "tener"), ("tienes", "tener"), ("tiene", "tener"), ("tenemos", "tener"),
    ("tenéis", "tener"), ("tienen", "tener"), ("tuve", "tener"), ("tuvo", "tener"),
    ("tuvieron", "tener"), ("tendré", "tener"), ("tendrá", "tener"), ("tendría", "tener"),
    ("tenga", "tener"), ("tengamos", "tener"), ("ten", "tener"), ("tened", "tener"),
    ("tenido", "tener"), ("teniendo", "tener"),
    ("hago", "hacer"), ("haces", "hacer"), ("hice", "hacer"), ("hizo", "hacer"),
    ("haré", "hacer"), ("haría", "hacer"), ("haga", "hacer"), ("haz", "hacer"),
    ("hecho", "hacer"), ("haciendo", "hacer"), ("haced", "hacer"),
    ("voy", "ir"), ("vas", "ir"), ("va", "ir"), ("vamos", "ir"), ("vais", "ir"), ("van", "ir"),
    ("fui", "ir"), ("fue", "ir"), ("fuimos", "ir"), ("fuiste", "ir"), ("fuisteis", "ir"),
    ("fueron", "ir"), ("iba", "ir"), ("íbamos", "ir"), ("iré", "ir"), ("iría", "ir"),
    ("vaya", "ir"), ("id", "ir"), ("yendo", "ir"), ("ido", "ir"),
    ("soy", "ser"), ("eres", "ser"), ("es", "ser"), ("eran", "ser"), ("éramos", "ser"),
    ("seré", "ser"), ("sea", "ser"), ("sido", "ser"), ("siendo", "ser"), ("sed", "ser"),
    ("estoy", "estar"), ("estás", "estar"), ("está", "estar"), ("estuve", "estar"),
    ("estuvo", "estar"), ("esté", "estar"), ("estad", "estar"), ("estando", "estar"),
    ("estado", "estar"),
    ("he", "haber"), ("has", "haber"), ("ha", "haber"), ("hay", "haber"), ("hemos", "haber"),
    ("habéis", "haber"), ("han", "haber"), ("hube", "haber"), ("hubo", "haber"),
    ("habré", "haber"), ("haya", "haber"), ("habido", "haber"), ("habiendo", "haber"),
    ("doy", "dar"), ("das", "dar"), ("da", "dar"), ("damos", "dar"), ("dais", "dar"),
    ("dan", "dar"), ("diste", "dar"), ("dio", "dar"), ("dimos", "dar"), ("disteis", "dar"),
    ("dieron", "dar"), ("daba", "dar"), ("daré", "dar"), ("daría", "dar"), ("dé", "dar"),
    ("des", "dar"), ("demos", "dar"), ("deis", "dar"), ("den", "dar"), ("dad", "dar"),
    ("dado", "dar"), ("dando", "dar"),
    ("veo", "ver"), ("ves", "ver"), ("ve", "ver"), ("vemos", "ver"), ("veis", "ver"),
    ("vi", "ver"), ("vio", "ver"), ("vimos", "ver"), ("visteis", "ver"), ("vieron", "ver"),
    ("veía", "ver"), ("veré", "ver"), ("vea", "ver"), ("ved", "ver"), ("visto", "ver"),
    ("viendo", "ver"),
    ("sé", "saber"), ("sabes", "saber"), ("sabe", "saber"), ("sabemos", "saber"),
    ("sabéis", "saber"), ("saben", "saber"), ("supe", "saber"), ("supo", "saber"),
    ("sabré", "saber"), ("sepa", "saber"), ("sabido", "saber"), ("sabiendo", "saber"),
    ("quiero", "querer"), ("quiere", "querer"), ("quise", "querer"), ("quiso", "querer"),
    ("querré", "querer"), ("querría", "querer"), ("quiera", "querer"), ("querido", "querer"),
    ("queriendo", "querer"),
    ("pongo", "poner"), ("pones", "poner"), ("puse", "poner"), ("puso", "poner"),
    ("pondré", "poner"), ("pondría", "poner"), ("ponga", "poner"), ("pon", "poner"),
    ("poned", "poner"), ("puesto", "poner"), ("poniendo", "poner"),
    ("traigo", "traer"), ("traes", "traer"), ("traje", "traer"), ("trajo", "traer"),
    ("traeré", "traer"), ("traiga", "traer"), ("trae", "traer"), ("traído", "traer"),
    ("trayendo", "traer"),
    ("salgo", "salir"), ("sales", "salir"), ("saldré", "salir"), ("salga", "salir"),
    ("sal", "salir"), ("salid", "salir"), ("salido", "salir"), ("saliendo", "salir"),
    ("vengo", "venir"), ("vienes", "venir"), ("vine", "venir"), ("vino", "venir"),
    ("vendré", "venir"), ("venga", "venir"), ("venid", "venir"), ("venido", "venir"),
    ("viniendo", "venir"),
    ("puedo", "poder"), ("puede", "poder"), ("pude", "poder"), ("pudo", "poder"),
    ("podré", "poder"), ("podría", "poder"), ("pueda", "poder"), ("podamos", "poder"),
    ("podido", "poder"), ("pudiendo", "poder"),
    ("digo", "decir"), ("dices", "decir"), ("dice", "decir"), ("dije", "decir"),
    ("dijo", "decir"), ("diré", "decir"), ("diría", "decir"), ("diga", "decir"),
    ("decid", "decir"), ("dicho", "decir"), ("diciendo", "decir"),
    # cambios de raiz
    ("sigo", "seguir"), ("sigues", "seguir"), ("sigue", "seguir"), ("seguimos", "seguir"),
    ("siguió", "seguir"), ("siguieron", "seguir"), ("siga", "seguir"), ("sigamos", "seguir"),
    ("siguiendo", "seguir"), ("seguido", "seguir"),
    ("consigo", "conseguir"), ("consigues", "conseguir"), ("consiguió", "conseguir"),
    ("consigamos", "conseguir"), ("consiguiendo", "conseguir"), ("conseguido", "conseguir"),
    ("siento", "sentir"), ("sientes", "sentir"), ("sintió", "sentir"),
    ("sintieron", "sentir"), ("sienta", "sentir"), ("sintamos", "sentir"),
    ("sintiendo", "sentir"), ("sentido", "sentir"),
    ("sirvo", "servir"), ("sirves", "servir"), ("sirvió", "servir"), ("sirvamos", "servir"),
    ("sirviendo", "servir"), ("servido", "servir"),
    ("visto", "ver"), ("vistes", "vestir"), ("vistió", "vestir"), ("vistamos", "vestir"),
    ("vistiendo", "vestir"), ("vestido", "vestir"),
    ("pido", "pedir"), ("pides", "pedir"), ("pidió", "pedir"), ("pidieron", "pedir"),
    ("pida", "pedir"), ("pidamos", "pedir"), ("pidiendo", "pedir"), ("pedido", "pedir"),
    ("repito", "repetir"), ("repitió", "repetir"), ("repitamos", "repetir"),
    ("repitiendo", "repetir"), ("repetido", "repetir"),
    ("mido", "medir"), ("midió", "medir"), ("midamos", "medir"), ("midiendo", "medir"),
    ("medido", "medir"),
    ("duermo", "dormir"), ("duermes", "dormir"), ("durmió", "dormir"),
    ("durmieron", "dormir"), ("duerma", "dormir"), ("durmamos", "dormir"),
    ("durmiendo", "dormir"), ("dormido", "dormir"),
    ("muero", "morir"), ("murió", "morir"), ("murieron", "morir"), ("muera", "morir"),
    ("muramos", "morir"), ("muriendo", "morir"), ("muerto", "morir"),
    ("juego", "jugar"), ("juegas", "jugar"), ("jugué", "jugar"), ("jugó", "jugar"),
    ("juegue", "jugar"), ("juguemos", "jugar"), ("jugando", "jugar"), ("jugado", "jugar"),
    ("pienso", "pensar"), ("piensas", "pensar"), ("pensé", "pensar"), ("pensó", "pensar"),
    ("piense", "pensar"), ("pensemos", "pensar"), ("pensando", "pensar"),
    ("cierro", "cerrar"), ("cerré", "cerrar"), ("cierre", "cerrar"), ("cerremos", "cerrar"),
    ("cerrado", "cerrar"),
    ("empiezo", "empezar"), ("empecé", "empezar"), ("empiece", "empezar"),
    ("empecemos", "empezar"), ("empezando", "empezar"), ("empezado", "empezar"),
    ("comienzo", "comenzar"), ("comencé", "comenzar"), ("comience", "comenzar"),
    ("comencemos", "comenzar"),
    ("entiendo", "entender"), ("entendí", "entender"), ("entienda", "entender"),
    ("entendamos", "entender"), ("entendido", "entender"),
    ("pierdo", "perder"), ("perdí", "perder"), ("pierda", "perder"), ("perdamos", "perder"),
    ("perdido", "perder"),
    ("prefiero", "preferir"), ("prefieres", "preferir"), ("prefirió", "preferir"),
    ("prefirieron", "preferir"), ("prefiera", "preferir"), ("prefiramos", "preferir"),
    ("prefiriendo", "preferir"), ("preferido", "preferir"),
    ("miento", "mentir"), ("mintió", "mentir"), ("mintieron", "mentir"),
    ("mienta", "mentir"), ("mintamos", "mentir"), ("mintiendo", "mentir"),
    ("mentido", "mentir"),
    ("convierto", "convertir"), ("convirtió", "convertir"), ("convierta", "convertir"),
    ("convirtamos", "convertir"), ("convirtiendo", "convertir"), ("convertido", "convertir"),
    ("vuelvo", "volver"), ("vuelve", "volver"), ("volví", "volver"), ("volvió", "volver"),
    ("vuelva", "volver"), ("volvamos", "volver"), ("volviendo", "volver"), ("vuelto", "volver"),
    ("vuelo", "volar"), ("vuelas", "volar"), ("volé", "volar"), ("vuele", "volar"),
    ("volemos", "volar"), ("volando", "volar"), ("volado", "volar"),
    ("cuento", "contar"), ("conté", "contar"), ("cuente", "contar"),
    ("contemos", "contar"), ("contando", "contar"), ("contado", "contar"),
    ("encuentro", "encontrar"), ("encontré", "encontrar"), ("encuentre", "encontrar"),
    ("encontremos", "encontrar"), ("encontrado", "encontrar"),
    ("recuerdo", "recordar"), ("recordé", "recordar"), ("recuerde", "recordar"),
    ("recordemos", "recordar"), ("recordado", "recordar"),
    ("muestro", "mostrar"), ("mostré", "mostrar"), ("muestre", "mostrar"),
    ("mostremos", "mostrar"), ("mostrado", "mostrar"),
    ("pruebo", "probar"), ("probé", "probar"), ("pruebe", "probar"), ("probemos", "probar"),
    ("probado", "probar"),
    ("sueño", "soñar"), ("soñé", "soñar"), ("sueñe", "soñar"), ("soñemos", "soñar"),
    ("soñado", "soñar"),
    ("llueve", "llover"), ("llovió", "llover"), ("llovía", "llover"), ("lloverá", "llover"),
    ("llovería", "llover"), ("llueva", "llover"), ("lloviendo", "llover"), ("llovido", "llover"),
    ("muevo", "mover"), ("moví", "mover"), ("mueva", "mover"), ("movamos", "mover"),
    ("moviendo", "mover"), ("movido", "mover"),
    ("huelo", "oler"), ("huele", "oler"), ("olemos", "oler"), ("oléis", "oler"),
    ("huelen", "oler"), ("olí", "oler"), ("olió", "oler"), ("oliste", "oler"),
    ("huela", "oler"), ("olamos", "oler"), ("oliendo", "oler"), ("olido", "oler"),
    ("valgo", "valer"), ("vales", "valer"), ("valdré", "valer"), ("valga", "valer"),
    ("valido", "valer"), ("valiendo", "valer"),
    ("quepo", "caber"), ("cabes", "caber"), ("cupe", "caber"), ("cupo", "caber"),
    ("cabré", "caber"), ("quepa", "caber"), ("cabido", "caber"), ("cabiendo", "caber"),
    ("caigo", "caer"), ("caes", "caer"), ("caí", "caer"), ("caíste", "caer"),
    ("cayó", "caer"), ("cayeron", "caer"), ("caiga", "caer"), ("cayendo", "caer"),
    ("caído", "caer"),
    ("oigo", "oír"), ("oyes", "oír"), ("oye", "oír"), ("oímos", "oír"), ("oís", "oír"),
    ("oyen", "oír"), ("oí", "oír"), ("oíste", "oír"), ("oyó", "oír"), ("oiga", "oír"),
    ("oído", "oír"), ("oyendo", "oír"), ("oíd", "oír"),
    ("huyo", "huir"), ("huyes", "huir"), ("huís", "huir"), ("huí", "huir"),
    ("huyó", "huir"), ("huyeron", "huir"), ("huya", "huir"), ("huyamos", "huir"),
    ("huyendo", "huir"), ("huido", "huir"),
    ("construyo", "construir"), ("construyes", "construir"), ("construís", "construir"),
    ("construí", "construir"), ("construyó", "construir"), ("construyeron", "construir"),
    ("construya", "construir"), ("construyamos", "construir"),
    ("construyendo", "construir"), ("construido", "construir"),
    ("incluyo", "incluir"), ("incluís", "incluir"), ("incluí", "incluir"),
    ("incluyó", "incluir"), ("incluyeron", "incluir"), ("incluya", "incluir"),
    ("incluyendo", "incluir"), ("incluido", "incluir"),
    ("leo", "leer"), ("lees", "leer"), ("leemos", "leer"), ("leí", "leer"),
    ("leíste", "leer"), ("leyó", "leer"), ("leyeron", "leer"), ("lea", "leer"),
    ("leamos", "leer"), ("leído", "leer"), ("leyendo", "leer"),
    ("creo", "creer"), ("crees", "creer"), ("creí", "creer"), ("creyó", "creer"),
    ("crea", "creer"), ("creído", "creer"), ("creyendo", "creer"),
    ("poseo", "poseer"), ("poseí", "poseer"), ("poseyó", "poseer"), ("posea", "poseer"),
    ("poseído", "poseer"), ("poseyendo", "poseer"),
    ("río", "reír"), ("ríes", "reír"), ("ríe", "reír"), ("reímos", "reír"), ("reís", "reír"),
    ("ríen", "reír"), ("reí", "reír"), ("reíste", "reír"), ("rió", "reír"),
    ("rieron", "reír"), ("ría", "reír"), ("riamos", "reír"), ("riendo", "reír"),
    ("reído", "reír"),
    ("sonrío", "sonreír"), ("sonríes", "sonreír"), ("sonreís", "sonreír"),
    ("sonreí", "sonreír"), ("sonrió", "sonreír"), ("sonrieron", "sonreír"),
    ("sonría", "sonreír"), ("sonriamos", "sonreír"), ("sonriendo", "sonreír"),
    ("sonreído", "sonreír"),
    ("frío", "freír"), ("fríes", "freír"), ("freímos", "freír"), ("freís", "freír"),
    ("fríen", "freír"), ("freí", "freír"), ("frió", "freír"), ("frieron", "freír"),
    ("fría", "freír"), ("friamos", "freír"), ("friendo", "freír"), ("frito", "freír"),
    ("freído", "freír"),
    ("produzco", "producir"), ("produces", "producir"), ("produje", "producir"),
    ("produjo", "producir"), ("produjeron", "producir"), ("produzca", "producir"),
    ("produciendo", "producir"), ("producido", "producir"),
    ("traduzco", "traducir"), ("traduje", "traducir"), ("tradujo", "traducir"),
    ("traduzca", "traducir"), ("traducido", "traducir"),
    ("conduzco", "conducir"), ("conduje", "conducir"), ("condujo", "conducir"),
    ("conduzca", "conducir"), ("conducido", "conducir"),
    ("conozco", "conocer"), ("conoces", "conocer"), ("conocí", "conocer"),
    ("conoció", "conocer"), ("conozca", "conocer"), ("conozcamos", "conocer"),
    ("conociendo", "conocer"), ("conocido", "conocer"),
    ("parezco", "parecer"), ("pareces", "parecer"), ("pareció", "parecer"),
    ("parezca", "parecer"), ("parecido", "parecer"),
    ("agradezco", "agradecer"), ("agradeció", "agradecer"), ("agradezca", "agradecer"),
    ("agradecido", "agradecer"),
    ("crezco", "crecer"), ("creció", "crecer"), ("crezca", "crecer"), ("crecido", "crecer"),
    ("nazco", "nacer"), ("nació", "nacer"), ("nazca", "nacer"), ("nacido", "nacer"),
    ("padezco", "padecer"), ("padeció", "padecer"), ("padezca", "padecer"),
    ("padecido", "padecer"),
    ("ofrezco", "ofrecer"), ("ofreció", "ofrecer"), ("ofrezca", "ofrecer"),
    ("ofrecido", "ofrecer"),
    ("permanezco", "permanecer"), ("permaneció", "permanecer"),
    ("permanezca", "permanecer"), ("permanecido", "permanecer"),
    ("pertenezco", "pertenecer"), ("perteneció", "pertenecer"),
    ("pertenezca", "pertenecer"), ("pertenecido", "pertenecer"),
    ("aparezco", "aparecer"), ("apareció", "aparecer"), ("aparezca", "aparecer"),
    ("aparecido", "aparecer"),
    ("ando", "andar"), ("anduve", "andar"), ("anduvo", "andar"), ("anduvieron", "andar"),
    ("andando", "andar"), ("andado", "andar"),
    ("satisfago", "satisfacer"), ("satisfaces", "satisfacer"), ("satisface", "satisfacer"),
    ("satisfice", "satisfacer"), ("satisfizo", "satisfacer"),
    ("satisfaré", "satisfacer"), ("satisfaga", "satisfacer"), ("satisfaz", "satisfacer"),
    ("satisfecho", "satisfacer"), ("satisfaciendo", "satisfacer"),
    ("bendigo", "bendecir"), ("bendices", "bendecir"), ("bendije", "bendecir"),
    ("bendijo", "bendecir"), ("bendiga", "bendecir"), ("bendito", "bendecir"),
    ("bendecido", "bendecir"), ("bendiciendo", "bendecir"),
    ("maldigo", "maldecir"), ("maldices", "maldecir"), ("maldije", "maldecir"),
    ("maldijo", "maldecir"), ("maldiga", "maldecir"), ("maldito", "maldecir"),
    ("maldecido", "maldecir"), ("maldiciendo", "maldecir"),
    ("escribo", "escribir"), ("escribí", "escribir"), ("escribió", "escribir"),
    ("escriba", "escribir"), ("escrito", "escribir"), ("escribiendo", "escribir"),
    ("descrito", "describir"), ("describo", "describir"),
    ("abro", "abrir"), ("abierto", "abrir"), ("abriendo", "abrir"),
    ("cubro", "cubrir"), ("cubierto", "cubrir"), ("cubriendo", "cubrir"),
    ("rompo", "romper"), ("roto", "romper"), ("rompiendo", "romper"),
    ("imprimo", "imprimir"), ("impreso", "imprimir"), ("imprimido", "imprimir"),
    ("imprimiendo", "imprimir"),
    ("resuelvo", "resolver"), ("resolví", "resolver"), ("resolvió", "resolver"),
    ("resuelva", "resolver"), ("resolvamos", "resolver"), ("resuelto", "resolver"),
    ("resolviendo", "resolver"),
    ("devuelvo", "devolver"), ("devolvió", "devolver"), ("devuelva", "devolver"),
    ("devolvamos", "devolver"), ("devuelto", "devolver"), ("devolviendo", "devolver"),
    ("envuelvo", "envolver"), ("envolvió", "envolver"), ("envuelva", "envolver"),
    ("envuelto", "envolver"), ("envolviendo", "envolver"),
    # -iar / -uar con hiato acentuado
    ("envío", "enviar"), ("envías", "enviar"), ("envía", "enviar"), ("enviamos", "enviar"),
    ("enviáis", "enviar"), ("envían", "enviar"), ("envié", "enviar"), ("enviaste", "enviar"),
    ("envió", "enviar"), ("envíe", "enviar"), ("enviemos", "enviar"), ("enviéis", "enviar"),
    ("envíen", "enviar"), ("enviando", "enviar"), ("enviado", "enviar"),
    ("confío", "confiar"), ("confías", "confiar"), ("confió", "confiar"),
    ("confíe", "confiar"), ("confiemos", "confiar"), ("confiéis", "confiar"),
    ("confíen", "confiar"), ("confiado", "confiar"),
    ("esquío", "esquiar"), ("esquías", "esquiar"), ("esquió", "esquiar"),
    ("esquíe", "esquiar"), ("esquiemos", "esquiar"), ("esquiéis", "esquiar"),
    ("esquíen", "esquiar"), ("esquiando", "esquiar"), ("esquiado", "esquiar"),
    ("actúo", "actuar"), ("actúas", "actuar"), ("actúa", "actuar"), ("actuamos", "actuar"),
    ("actuáis", "actuar"), ("actúan", "actuar"), ("actué", "actuar"), ("actuó", "actuar"),
    ("actúe", "actuar"), ("actuemos", "actuar"), ("actuéis", "actuar"), ("actúen", "actuar"),
    ("actuando", "actuar"), ("actuado", "actuar"),
    ("continúo", "continuar"), ("continúa", "continuar"), ("continué", "continuar"),
    ("continuó", "continuar"), ("continúe", "continuar"), ("continuemos", "continuar"),
    ("continuéis", "continuar"), ("continúen", "continuar"),
    ("gradúo", "graduar"), ("graduó", "graduar"), ("gradúe", "graduar"),
    ("graduemos", "graduar"), ("graduéis", "graduar"), ("gradúen", "graduar"),
    ("sitúo", "situar"), ("situó", "situar"), ("sitúe", "situar"), ("situemos", "situar"),
    ("situéis", "situar"), ("sitúen", "situar"),
    ("averiguo", "averiguar"), ("averiguas", "averiguar"), ("averiguáis", "averiguar"),
    ("averigüé", "averiguar"), ("averiguó", "averiguar"), ("averigüe", "averiguar"),
    ("averigüemos", "averiguar"), ("averigüéis", "averiguar"), ("averigüen", "averiguar"),
    ("averiguando", "averiguar"), ("averiguado", "averiguar"),
    ("avergüenzo", "avergonzar"), ("avergüenzas", "avergonzar"),
    ("avergonzamos", "avergonzar"), ("avergoncé", "avergonzar"),
    ("avergonzó", "avergonzar"), ("avergüence", "avergonzar"),
    ("avergoncemos", "avergonzar"), ("avergoncéis", "avergonzar"),
    ("avergüencen", "avergonzar"), ("avergonzando", "avergonzar"),
    ("avergonzado", "avergonzar"),
    # g->j
    ("cojo", "coger"), ("coges", "coger"), ("coge", "coger"), ("cogemos", "coger"),
    ("cogéis", "coger"), ("cogen", "coger"), ("cogí", "coger"), ("cogió", "coger"),
    ("coja", "coger"), ("cojamos", "coger"), ("cogiendo", "coger"), ("cogido", "coger"),
    ("recojo", "recoger"), ("recogí", "recoger"), ("recogió", "recoger"), ("recoja", "recoger"),
    ("recogiendo", "recoger"), ("recogido", "recoger"),
    ("elijo", "elegir"), ("eliges", "elegir"), ("elige", "elegir"),
    ("elegimos", "elegir"), ("eligió", "elegir"), ("eligieron", "elegir"),
    ("elija", "elegir"), ("elijamos", "elegir"), ("eligiendo", "elegir"),
    ("elegido", "elegir"),
    ("corrijo", "corregir"), ("corriges", "corregir"), ("corrigió", "corregir"),
    ("corrija", "corregir"), ("corrijamos", "corregir"), ("corrigiendo", "corregir"),
    ("corregido", "corregir"),
    ("rijo", "regir"), ("riges", "regir"), ("rigió", "regir"), ("rija", "regir"),
    ("rijamos", "regir"), ("rigiendo", "regir"), ("regido", "regir"),
    ("dirijo", "dirigir"), ("diriges", "dirigir"), ("dirigió", "dirigir"),
    ("dirija", "dirigir"), ("dirijamos", "dirigir"), ("dirigiendo", "dirigir"),
    ("dirigido", "dirigir"),
    ("exijo", "exigir"), ("exiges", "exigir"), ("exigió", "exigir"), ("exija", "exigir"),
    ("exijamos", "exigir"), ("exigiendo", "exigir"), ("exigido", "exigir"),
    ("surjo", "surgir"), ("surges", "surgir"), ("surgió", "surgir"), ("surja", "surgir"),
    ("surjamos", "surgir"), ("surgiendo", "surgir"), ("surgido", "surgir"),
    ("urjo", "urgir"), ("urges", "urgir"), ("urgió", "urgir"), ("urja", "urgir"),
    ("urjamos", "urgir"), ("urgiendo", "urgir"), ("urgido", "urgir"),
    ("esparzo", "esparcir"), ("esparces", "esparcir"), ("esparció", "esparcir"),
    ("esparza", "esparcir"), ("esparzamos", "esparcir"), ("esparciendo", "esparcir"),
    ("esparcido", "esparcir"),
    ("luzco", "lucir"), ("luces", "lucir"), ("lució", "lucir"), ("luzca", "lucir"),
    ("luzcamos", "lucir"), ("luciendo", "lucir"), ("lucido", "lucir"),
    ("venzo", "vencer"), ("vences", "vencer"), ("venció", "vencer"), ("venza", "vencer"),
    ("venzamos", "vencer"), ("venciendo", "vencer"), ("vencido", "vencer"),
    ("mezo", "mecer"), ("meces", "mecer"), ("meció", "mecer"), ("meza", "mecer"),
    ("mezamos", "mecer"), ("meciendo", "mecer"), ("mecido", "mecer"),
    # z->c / c->qu
    ("cazo", "cazar"), ("cacé", "cazar"), ("cazó", "cazar"), ("cace", "cazar"),
    ("cacemos", "cazar"), ("cazando", "cazar"), ("cazado", "cazar"),
    ("cruzo", "cruzar"), ("crucé", "cruzar"), ("cruce", "cruzar"), ("crucemos", "cruzar"),
    ("cruzando", "cruzar"), ("cruzado", "cruzar"),
    ("realizo", "realizar"), ("realicé", "realizar"), ("realice", "realizar"),
    ("realicemos", "realizar"), ("realizando", "realizar"), ("realizado", "realizar"),
    ("analizo", "analizar"), ("analicé", "analizar"), ("analice", "analizar"),
    ("utilizo", "utilizar"), ("utilicé", "utilizar"), ("utilice", "utilizar"),
    ("actualizo", "actualizar"), ("actualicé", "actualizar"), ("actualice", "actualizar"),
    ("autorizo", "autorizar"), ("autoricé", "autorizar"), ("autorice", "autorizar"),
    ("armonizo", "armonizar"), ("armonicé", "armonizar"), ("armonice", "armonizar"),
    ("arranco", "arrancar"), ("arranqué", "arrancar"), ("arranque", "arrancar"),
    ("arranquemos", "arrancar"), ("arrancando", "arrancar"), ("arrancado", "arrancar"),
    ("toco", "tocar"), ("toqué", "tocar"), ("toque", "tocar"), ("toquemos", "tocar"),
    ("tocando", "tocar"), ("tocado", "tocar"),
    ("busco", "buscar"), ("busqué", "buscar"), ("buscó", "buscar"), ("busque", "buscar"),
    ("busquemos", "buscar"), ("buscando", "buscar"), ("buscado", "buscar"),
    ("saco", "sacar"), ("saqué", "sacar"), ("saque", "sacar"),
    ("explico", "explicar"), ("expliqué", "explicar"), ("explique", "explicar"),
    ("practico", "practicar"), ("practiqué", "practicar"), ("practique", "practicar"),
    ("aplico", "aplicar"), ("apliqué", "aplicar"), ("aplique", "aplicar"),
    ("dedico", "dedicar"), ("dediqué", "dedicar"), ("dedique", "dedicar"),
    ("indico", "indicar"), ("indiqué", "indicar"), ("indique", "indicar"),
    ("comunico", "comunicar"), ("comuniqué", "comunicar"), ("comunique", "comunicar"),
    ("educo", "educar"), ("eduqué", "educar"), ("eduque", "educar"),
    ("pesco", "pescar"), ("pesqué", "pescar"), ("pesque", "pescar"),
    ("aparca", "aparcar"), ("aparqué", "aparcar"), ("aparque", "aparcar"),
    ("aparcamos", "aparcar"),
    ("acerco", "acercar"), ("acerqué", "acercar"), ("acerque", "acercar"),
    ("acerquemos", "acercar"), ("acercando", "acercar"), ("acercado", "acercar"),
    ("justifico", "justificar"), ("justifiqué", "justificar"), ("justifique", "justificar"),
    ("identifico", "identificar"), ("identifiqué", "identificar"),
    ("identifique", "identificar"),
    ("clasifico", "clasificar"), ("clasifiqué", "clasificar"), ("clasifique", "clasificar"),
    ("simplifico", "simplificar"), ("simplifiqué", "simplificar"),
    ("simplifique", "simplificar"),
    ("verifico", "verificar"), ("verifiqué", "verificar"), ("verifique", "verificar"),
    ("certifico", "certificar"), ("certifiqué", "certificar"), ("certifique", "certificar"),
    # extra
    ("acuesto", "acostar"), ("acuestas", "acostar"), ("acostamos", "acostar"),
    ("acosté", "acostar"), ("acueste", "acostar"), ("acostemos", "acostar"),
    ("acostando", "acostar"), ("acostado", "acostar"),
    ("despierto", "despertar"), ("despiertas", "despertar"), ("desperté", "despertar"),
    ("despierte", "despertar"), ("despertemos", "despertar"), ("despertando", "despertar"),
    ("despertado", "despertar"),
    ("divierto", "divertir"), ("divertimos", "divertir"), ("divirtió", "divertir"),
    ("divierta", "divertir"), ("divirtamos", "divertir"), ("divirtiendo", "divertir"),
    ("divertido", "divertir"),
    ("adquiero", "adquirir"), ("adquieres", "adquirir"), ("adquiere", "adquirir"),
    ("adquirimos", "adquirir"), ("adquirió", "adquirir"), ("adquiera", "adquirir"),
    ("adquiramos", "adquirir"), ("adquiriendo", "adquirir"), ("adquirido", "adquirir"),

    # 1p/2p del subjuntivo (donde se pierde el diptongo y fallan los motores ingenuos)
    ("tengamos", "tener"), ("podamos", "poder"), ("queramos", "querer"),
    ("traigamos", "traer"), ("salgamos", "salir"), ("valgamos", "valer"),
    ("quepamos", "caber"), ("caigamos", "caer"), ("oigamos", "oír"),
    ("vengamos", "venir"), ("digamos", "decir"), ("hagamos", "hacer"),
    ("pongamos", "poner"), ("satisfagamos", "satisfacer"), ("bendigamos", "bendecir"),
    ("maldigamos", "maldecir"), ("produzcamos", "producir"),
    ("traduzcamos", "traducir"), ("conduzcamos", "conducir"),
    ("veamos", "ver"), ("seamos", "ser"), ("vayamos", "ir"), ("estemos", "estar"),
    ("hayamos", "haber"), ("demos", "dar"), ("sepamos", "saber"), ("leamos", "leer"),
    ("creamos", "creer"), ("poseamos", "poseer"), ("huyamos", "huir"),
    ("construyamos", "construir"), ("incluyamos", "incluir"), ("riamos", "reír"),
    ("sonriamos", "sonreír"), ("friamos", "freír"), ("enviemos", "enviar"),
    ("confiemos", "confiar"), ("esquiemos", "esquiar"), ("actuemos", "actuar"),
    ("continuemos", "continuar"), ("graduemos", "graduar"), ("situemos", "situar"),
    ("enviéis", "enviar"), ("actuéis", "actuar"), ("estéis", "estar"), ("deis", "dar"),
    ("juguemos", "jugar"), ("pensemos", "pensar"), ("empecemos", "empezar"),
    ("comencemos", "comenzar"), ("entendamos", "entender"), ("perdamos", "perder"),
    ("volvamos", "volver"), ("contemos", "contar"), ("encontremos", "encontrar"),
    ("recordemos", "recordar"), ("mostremos", "mostrar"), ("probemos", "probar"),
    ("soñemos", "soñar"), ("movamos", "mover"), ("resolvamos", "resolver"),
    ("devolvamos", "devolver"), ("envolvamos", "envolver"), ("almorcemos", "almorzar"),
    ("tropecemos", "tropezar"), ("olamos", "oler"), ("acostemos", "acostar"),
    ("despertemos", "despertar"), ("divirtamos", "divertir"), ("adquiramos", "adquirir"),
    ("vistamos", "vestir"), ("repitamos", "repetir"), ("midamos", "medir"),
    ("pidamos", "pedir"), ("sirvamos", "servir"), ("durmamos", "dormir"),
    ("muramos", "morir"), ("sintamos", "sentir"), ("prefiramos", "preferir"),
    ("mintamos", "mentir"), ("convirtamos", "convertir"), ("sigamos", "seguir"),
    ("consigamos", "conseguir"), ("cojamos", "coger"), ("elijamos", "elegir"),
    ("corrijamos", "corregir"), ("rijamos", "regir"), ("dirijamos", "dirigir"),
    ("exijamos", "exigir"), ("surjamos", "surgir"), ("urjamos", "urgir"),
    ("esparzamos", "esparcir"), ("luzcamos", "lucir"), ("venzamos", "vencer"),
    ("mezamos", "mecer"), ("conozcamos", "conocer"),
    ("cacemos", "cazar"), ("crucemos", "cruzar"), ("realicemos", "realizar"),
    ("analicemos", "analizar"), ("utilicemos", "utilizar"), ("actualicemos", "actualizar"),
    ("autoricemos", "autorizar"), ("armonicemos", "armonizar"), ("arranquemos", "arrancar"),
    ("toquemos", "tocar"), ("busquemos", "buscar"), ("saquemos", "sacar"),
    ("expliquemos", "explicar"), ("practiquemos", "practicar"), ("apliquemos", "aplicar"),
    ("dediquemos", "dedicar"), ("indiquemos", "indicar"), ("comuniquemos", "comunicar"),
    ("eduquemos", "educar"), ("pesquemos", "pescar"), ("aparquemos", "aparcar"),
    ("acerquemos", "acercar"), ("justifiquemos", "justificar"),
    ("identifiquemos", "identificar"), ("clasifiquemos", "clasificar"),
    ("simplifiquemos", "simplificar"), ("verifiquemos", "verificar"),
    ("certifiquemos", "certificar"), ("averigüemos", "averiguar"),
    ("avergoncemos", "avergonzar"), ("andemos", "andar"),

    # futuro y condicional (raiz irregular y oír/reír sin tilde)
    ("tendrás", "tener"), ("tendríamos", "tener"), ("haréis", "hacer"), ("harían", "hacer"),
    ("dirán", "decir"), ("diríamos", "decir"), ("vendré", "venir"), ("vendrían", "venir"),
    ("sabrás", "saber"), ("pondré", "poner"), ("pondrían", "poner"),
    ("querrán", "querer"), ("querríamos", "querer"), ("cabrá", "caber"), ("cabrían", "caber"),
    ("valdrá", "valer"), ("valdrían", "valer"), ("habrá", "haber"), ("habrían", "haber"),
    ("saldrá", "salir"), ("saldrían", "salir"), ("podrás", "poder"), ("podrían", "poder"),
    ("satisfaré", "satisfacer"), ("satisfarían", "satisfacer"),
    ("oiré", "oír"), ("oirás", "oír"), ("oirá", "oír"), ("oiremos", "oír"),
    ("oiréis", "oír"), ("oirán", "oír"), ("oiría", "oír"), ("oirías", "oír"),
    ("reiré", "reír"), ("reirás", "reír"), ("reirá", "reír"), ("reiremos", "reír"),
    ("reiréis", "reír"), ("reirán", "reír"), ("reiría", "reír"),
    ("sonreiré", "sonreír"), ("sonreiría", "sonreír"),
    ("freiré", "freír"), ("freirás", "freír"), ("freiría", "freír"),
    ("irán", "ir"), ("serán", "ser"), ("estarán", "estar"), ("verán", "ver"),
    ("darán", "dar"), ("darían", "dar"), ("hará", "hacer"),
]

# formas que NO deben existir (errores tipicos de motor: tilde de mas, raiz mal formada)
NOT_PRESENT = [
    "oíré", "reíré", "freíré", "sonreíré", "oírás", "reíría",
    "tenjamos", "tenjáis", "puedamos", "puedáis", "quieramos", "traijamos",
    "venjamos", "averiggüé", "averigué", "averguence", "averguenzo",
    "eligo", "dirigo", "conozo", "venco", "cogo", "mezco", "esparco",
    "luco", "produzo", "conduzo", "traduzo", "andé", "conducí", "produzí",
    "tradució", "bendició", "satisfací", "habemos", "oyo", "oyí", "morido",
    "escribido", "abrido", "cubrido", "rompido", "volvido", "decido", "ponido",
    "haco", "vago", "sepo", "sabo", "valo", "cabo", "jugo",
]

A4 = [
    ("ve", "ver", "pres.", "3s"),          # vs. ir imper. 2s / ver imper. 2s
    ("ven", "ver", "pres.", "3p"),         # vs. venir imper. 2s
    ("sé", "saber", "pres.", "1s"),        # vs. ser imper. 2s
    ("di", "decir", "imper.", "2s"),       # vs. dar pret. 1s
    ("viste", "ver", "pret.", "2s"),       # vs. vestir pres. 3s
    ("fue", "ir", "pret.", "3s"),          # vs. ser pret. 3s
    ("fui", "ir", "pret.", "1s"),
    ("fueron", "ir", "pret.", "3p"),
    ("hay", "haber", "pres.", "3s"),
    ("dé", "dar", "subj.", "3s"),
    ("esté", "estar", "subj.", "3s"),
    ("vaya", "ir", "subj.", "3s"),
    ("sea", "ser", "subj.", "3s"),
    ("tenía", "tener", "imp.", "3s"),
    ("tendría", "tener", "cond.", "3s"),
    ("tenga", "tener", "subj.", "3s"),
    ("daba", "dar", "imp.", "3s"),
    ("busca", "buscar", "pres.", "3s"),    # vs. imper. 2s
]


def check(entries):
    fails = []
    for row in A2:
        f, inf = row[0], row[1]
        got = entries.get(f)
        if got is None:
            fails.append("%-16s ausente (esperado %s)" % (f, inf))
        elif got[0] != inf:
            fails.append("%-16s -> %s (esperado %s)" % (f, got[0], inf))
    for f, inf, t, p in A4:
        got = entries.get(f)
        if got is None:
            fails.append("%-16s ausente (esperado %s/%s/%s)" % (f, inf, t, p))
        elif got != (inf, t, p):
            fails.append("%-16s -> %s (esperado %s)" % (f, got, (inf, t, p)))
    for f in NOT_PRESENT:
        if f in entries:
            fails.append("%-16s NO deberia existir (-> %s)" % (f, entries[f]))
    return fails


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, os.pardir, "data", "lex_irregular.json")
    target = os.path.abspath(target)
    entries = main()
    fails = check(entries)
    if fails:
        sys.stdout.write("FALLOS (%d):\n" % len(fails))
        for f in fails:
            sys.stdout.write("  " + f + "\n")
        sys.exit(1)
    write_json(entries, target)
    sys.stdout.write("OK -> %s\n" % target)
    sys.stdout.write("entradas=%d  verbos=%d  aserciones=%d (+%d negativas)\n"
                     % (len(entries), len(VERBS), len(A2) + len(A4), len(NOT_PRESENT)))
