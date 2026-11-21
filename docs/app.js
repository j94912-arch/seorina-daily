const $ = id => document.getElementById(id);
const names = {all:'全部', news:'韓媒', x:'X', ig:'IG'};

const datefmt = v => {
    let t = new Date(v);
    return Number.isNaN(t.getTime()) ? v :
        new Intl.DateTimeFormat('zh-TW', {
            timeZone:'Asia/Taipei',
            dateStyle:'medium',
            timeStyle:'short'
        }).format(t);
};

let data, tab = 'all';

for (const [id, n] of Object.entries({
    all:names.all, news:names.news
})) {
    let b = document.createElement('button');
    b.textContent = n;
    b.onclick = () => {tab = id; render()};
    $('tabs').append(b);
}

function render() {
    if (!data) return;
    let root = $('feed');
    root.replaceChildren();
    let items = data.items.filter(x =>
        (tab === 'all' || x.source === tab) &&
        ($('history').checked ||
        x.batch === data.updated?.slice(0,10))
    ).reverse();

    if (!items.length)
        root.textContent = '此篩選沒有已收錄資料；請查看來源狀態。';

    for (let x of items) {
        let a = document.createElement('article'),
            s = document.createElement('small'),
            p = document.createElement('p'),
            l = document.createElement('a');

        s.textContent = names[x.source] + ' · ' + datefmt(x.date);
        p.textContent = x.title;
        l.textContent = '閱讀原文 ↗';

        try {
            let u = new URL(x.url);
            if (u.protocol === 'https:') l.href = u.href;
        } catch {}

        l.target = '_blank';
        l.rel = 'noopener noreferrer';
        a.append(s,p,l);
        root.append(a);
    }
}

$('history').onchange = render;

fetch('data.json', {cache:'no-store'})
    .then(r => {
        if (!r.ok) throw Error();
        return r.json();
    })
    .then(d => {
        data = d;
        $('status').textContent =
            (d.updated ?
            '最近更新：' + datefmt(d.updated) :
            '尚未執行蒐集') + '\n' +
            Object.entries(d.status || {})
            .filter(([k]) => k === 'news')
            .map(([k,v]) => names[k] + '：' + v)
            .join('｜');
        render();
    })
    .catch(() =>
        $('status').textContent = '資料載入失敗'
    );
