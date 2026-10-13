'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Home,
  Plus,
  Library,
  Folder,
  Search,
  Heart,
  LayoutGrid,
  List,
  Layers,
  ChevronRight,
  Menu,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Film,
  Clock,
  HardDrive,
  BookmarkPlus,
  FolderPlus,
  Pencil,
  Trash2,
  ShieldCheck,
  RefreshCw,
  Play,
} from 'lucide-react';
import {
  ApiError,
  api,
  activeJob,
  bytes,
  Cell,
  date,
  Group,
  Job,
  jobLabel,
  Media,
  Page,
  SearchResults,
  Stats,
  time,
  User,
} from '@/lib/api';
import { Modal } from './ui/dialog';
import { Logo } from './brand';
import { Login } from './login';
import { Organize } from './organize';
import { SettingsView } from './settings-view';
import { Confirm } from './ui/confirm';
import { MediaCard } from './media-card';
import { AddMedia } from './add-media';
import { MediaDetail } from './media-detail';
import { CellDetail } from './cell-detail';
import { BatchOrganize } from './batch-organize';
import { BatchDelete } from './batch-delete';
import { ShelfHeaderPicker } from './shelf-header-picker';
import { ShelfHeaderImage } from './shelf-header-image';
import { AccountMenu } from './account-menu';
import { ColorPicker } from './ui/color-picker';
import { LinkSharing } from './link-sharing';
import { ItemContextMenu, ContextAction } from './ui/context-menu';
import { allShelves } from '@/lib/groups';
import { HomeSculpture } from './home-sculpture';
import { ContentRail } from './content-rail';

export function Lumvia() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          mutations: { networkMode: 'always' },
          queries: {
            // The local library is reachable even when macOS reports no Internet connection.
            networkMode: 'always',
            retry: (count, error) =>
              !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && count < 1,
            refetchOnWindowFocus: true,
            staleTime: 5000,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  );
}
function App() {
  const mobileMenu = useRef<HTMLElement>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const wasMobileOpen = useRef(false);
  const query = useQueryClient();
  const params = useSearchParams();
  const router = useRouter();
  const view = params.get('view') || 'home',
    search = params.get('q') || '',
    shelfId = params.get('shelf') || '',
    collectionId = params.get('collection') || '',
    mediaId = params.get('media') || '',
    cellId = params.get('cell') || '',
    mode = params.get('tab') || 'videos';
  const [mobile, setMobile] = useState(false),
    [toast, setToast] = useState(''),
    [searchInput, setSearchInput] = useState(search),
    [sort, setSort] = useState('newest'),
    [grid, setGrid] = useState(true),
    [favorite, setFavorite] = useState(false),
    [offset, setOffset] = useState(0);
  useEffect(() => {
    if (mobile) mobileMenu.current?.querySelector<HTMLButtonElement>('button')?.focus();
    else if (wasMobileOpen.current) menuTrigger.current?.focus();
    wasMobileOpen.current = mobile;
  }, [mobile]);
  useEffect(() => {
    const breakpoint = window.matchMedia('(max-width: 760px)');
    const resized = () => {
      if (!breakpoint.matches) setMobile(false);
    };
    breakpoint.addEventListener('change', resized);
    return () => breakpoint.removeEventListener('change', resized);
  }, []);
  const [groupEditor, setGroupEditor] = useState<{ kind: 'shelves' | 'collections'; group?: Group } | null>(
      null,
    ),
    [groupDelete, setGroupDelete] = useState<{ kind: string; group: Group } | null>(null),
    [organize, setOrganize] = useState<Media | Cell | null>(null),
    [progressOpen, setProgressOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [addDestination, setAddDestination] = useState(
    shelfId ? `shelves:${shelfId}` : collectionId ? `collections:${collectionId}` : '',
  );
  const [context, setContext] = useState<{
    x: number;
    y: number;
    title: string;
    actions: ContextAction[];
  } | null>(null);
  const closeContext = useCallback(() => setContext(null), []);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Map<string, Media | Cell>>(() => new Map());
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [selectionAnchor, setSelectionAnchor] = useState<{ key: string; selected: boolean } | null>(null);
  const selectionTrigger = useRef<HTMLButtonElement>(null);
  const selecting = selectionMode && view === 'library' && !search;
  const endSelection = useCallback(() => {
    setSelectionMode(false);
    setSelectedItems(new Map());
    setSelectionAnchor(null);
    selectionTrigger.current?.focus();
  }, [setSelectionMode, setSelectedItems, setSelectionAnchor]);
  useEffect(() => {
    if (!selecting) return;
    const escape = (event: KeyboardEvent) => {
      if (
        event.key !== 'Escape' ||
        event.defaultPrevented ||
        document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"]')
      )
        return;
      event.preventDefault();
      endSelection();
    };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [selecting, endSelection]);
  function itemKey(item: Media | Cell) {
    return ('media_id' in item ? 'cell:' : 'media:') + item.id;
  }
  function toggleSelection(item: Media | Cell, shift = false) {
    const key = itemKey(item);
    const displayed: (Media | Cell)[] =
      mode === 'cells' ? (cells.data?.items ?? []) : (media.data?.items ?? []);
    const anchorIndex = displayed.findIndex((entry) => itemKey(entry) === selectionAnchor?.key);
    const targetIndex = displayed.findIndex((entry) => itemKey(entry) === key);
    if (shift && anchorIndex >= 0 && targetIndex >= 0 && selectionAnchor) {
      const next = new Map(selectedItems);
      for (const entry of displayed.slice(
        Math.min(anchorIndex, targetIndex),
        Math.max(anchorIndex, targetIndex) + 1,
      )) {
        if (selectionAnchor.selected) next.set(itemKey(entry), entry);
        else next.delete(itemKey(entry));
      }
      if (next.size > 100) {
        setToast('一度に選択できるのは100件までです');
        return;
      }
      setSelectedItems(next);
      return;
    }
    if (!selectedItems.has(key) && selectedItems.size >= 100) {
      setToast('一度に選択できるのは100件までです');
      return;
    }
    const next = new Map(selectedItems);
    if (next.has(key)) next.delete(key);
    else next.set(key, item);
    setSelectionAnchor({ key, selected: next.has(key) });
    setSelectedItems(next);
  }
  function itemContext(event: React.MouseEvent, item: Media | Cell) {
    event.preventDefault();
    event.stopPropagation();
    const multiple = selectedItems.has(itemKey(item)) ? [...selectedItems.values()] : [item];
    const chooseItems = () => {
      if (view !== 'library' || search)
        navigate({ view: 'library', tab: 'media_id' in item ? 'cells' : 'videos' });
      setSelectionMode(true);
      setSelectedItems(new Map(multiple.map((value) => [itemKey(value), value])));
    };
    const rect = event.currentTarget.getBoundingClientRect();
    const isCell = 'media_id' in item;
    setContext({
      x: event.clientX || rect.left,
      y: event.clientY || rect.top,
      title: multiple.length > 1 ? `${multiple.length}件を選択` : item.title,
      actions: [
        { label: '開く', run: () => (isCell ? openCell(item as Cell) : openMedia(item.id)) },
        ...(!isCell && multiple.length === 1
          ? [
              {
                label: (item as Media).favorite ? 'お気に入りを解除' : 'お気に入りに追加',
                run: () =>
                  void act(() =>
                    api('/media/' + item.id, {
                      method: 'PATCH',
                      body: JSON.stringify({ favorite: !(item as Media).favorite }),
                    }),
                  ),
              },
            ]
          : []),
        {
          label: multiple.length > 1 ? '選択した項目をShelfに追加' : 'Shelfに追加',
          run: () => {
            chooseItems();
            setBatchOpen(true);
          },
        },
        { label: '選択・複数選択を開始', run: chooseItems },
        {
          label: multiple.length > 1 ? '選択した項目を削除…' : '削除…',
          danger: true,
          run: () => {
            chooseItems();
            setBatchDeleteOpen(true);
          },
        },
      ],
    });
  }
  function shelfContext(event: React.MouseEvent, group: Group & { kind: 'shelves' | 'collections' }) {
    event.preventDefault();
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    setContext({
      x: event.clientX || rect.left,
      y: event.clientY || rect.top,
      title: group.name,
      actions: [
        {
          label: '開く',
          run: () =>
            navigate({ view: 'library', [group.kind === 'shelves' ? 'shelf' : 'collection']: group.id }),
        },
        { label: '名前・色・ヘッダーを編集', run: () => setGroupEditor({ kind: group.kind, group }) },
        { label: 'Shelfを削除…', danger: true, run: () => setGroupDelete({ kind: group.kind, group }) },
      ],
    });
  }
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<User>('/auth/me'), retry: false });
  const enabled = !!me.data;
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api<Page<Job>>('/jobs'),
    enabled,
    refetchInterval: 3000,
  });
  const running = jobs.data?.items.filter(activeJob) ?? [];
  const stats = useQuery({ queryKey: ['stats'], queryFn: () => api<Stats>('/library/stats'), enabled });
  const shelves = useQuery({
    queryKey: ['shelves'],
    queryFn: () => api<{ items: Group[] }>('/shelves'),
    enabled,
  });
  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: () => api<{ items: Group[] }>('/collections'),
    enabled,
  });
  const groups = allShelves(shelves.data?.items, collections.data?.items);
  const mediaQuery = new URLSearchParams({
    limit: view === 'home' ? '12' : '24',
    offset: String(offset),
    sort,
    favorite: String(favorite),
  });
  if (shelfId) mediaQuery.set('shelf_id', shelfId);
  if (collectionId) mediaQuery.set('collection_id', collectionId);
  const media = useQuery({
    queryKey: ['media', mediaQuery.toString()],
    queryFn: () => api<Page<Media>>('/media?' + mediaQuery),
    enabled,
    refetchInterval: running.length ? 2000 : false,
  });
  const cells = useQuery({
    queryKey: ['cells', shelfId, collectionId, offset],
    queryFn: () =>
      api<Page<Cell>>(
        `/cells?limit=24&offset=${offset}${collectionId ? '&collection_id=' + collectionId : ''}${shelfId ? '&shelf_id=' + shelfId : ''}`,
      ),
    enabled,
  });
  const results = useQuery({
    queryKey: ['search', search, offset],
    queryFn: () => api<SearchResults>(`/search?q=${encodeURIComponent(search)}&offset=${offset}`),
    enabled: enabled && !!search,
  });
  function navigate(values: Record<string, string>) {
    setSelectionAnchor(null);
    setSelectionMode(false);
    setSelectedItems(new Map());
    if (values.view === 'add')
      setAddDestination(
        values.shelf
          ? `shelves:${values.shelf}`
          : values.collection
            ? `collections:${values.collection}`
            : '',
      );
    const p = new URLSearchParams(values);
    router.push('/' + (p.size ? '?' + p.toString() : ''));
    setMobile(false);
    setOffset(0);
    setFavorite(false);
    setSearchInput(values.q || '');
  }
  function openMedia(id: string, start = 0, end?: number) {
    const p = new URLSearchParams(params);
    p.delete('cell');
    p.set('media', id);
    if (start) p.set('t', String(start));
    else p.delete('t');
    if (end !== undefined) p.set('end', String(end));
    else p.delete('end');
    router.push('/?' + p.toString());
  }
  function openCell(cell: Cell) {
    const p = new URLSearchParams(params);
    p.delete('media');
    p.delete('t');
    p.delete('end');
    p.set('cell', cell.id);
    router.push('/?' + p.toString());
  }
  function closeMedia() {
    const p = new URLSearchParams(params);
    p.delete('cell');
    p.delete('media');
    p.delete('t');
    p.delete('end');
    router.push('/?' + p.toString());
  }
  function refresh() {
    void query.invalidateQueries({
      predicate: (q) => q.queryKey[0] !== 'me' && q.queryKey[0] !== 'auth-options',
    });
  }
  async function act(action: () => Promise<unknown>, success?: string) {
    setBusy(true);
    setError('');
    try {
      await action();
      refresh();
      if (success) setToast(success);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  const jobsFingerprint = jobs.data?.items.map((j) => j.id + j.state).join('|');
  const previousJobs = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (previousJobs.current !== undefined && previousJobs.current !== jobsFingerprint) {
      void query.invalidateQueries({
        predicate: (q) => !['jobs', 'me', 'auth-options'].includes(String(q.queryKey[0])),
      });
    }
    previousJobs.current = jobsFingerprint;
  }, [jobsFingerprint, query]);
  useEffect(() => {
    const handle = () => {
      query.setQueryData(['me'], null);
      query.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' });
    };
    window.addEventListener('lumvia:unauthorized', handle);
    return () => window.removeEventListener('lumvia:unauthorized', handle);
  }, [query]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  const focusedGroup =
    view === 'library' || view === 'collections'
      ? (shelfId ? shelves.data?.items : collections.data?.items)?.find(
          (g) => g.id === (shelfId || collectionId),
        )
      : undefined;
  const title = search
    ? `「${search}」の検索結果`
    : (focusedGroup?.name ??
      ({
        home: 'ホーム',
        add: '動画を追加',
        library: 'ライブラリ',
        collections: 'Shelf',
        settings: '設定',
      }[view] ||
        'ライブラリ'));
  if (me.isPending)
    return (
      <div className="boot">
        <Logo large />
        <Loader2 className="spin" size={20} />
      </div>
    );
  if (!me.data) {
    if (me.isError && (!(me.error instanceof ApiError) || me.error.status !== 401))
      return (
        <main className="error-page">
          <Logo large />
          <h1>サーバーに接続できません</h1>
          <p>{me.error.message}</p>
          <button className="button primary" onClick={() => me.refetch()}>
            再接続
          </button>
        </main>
      );
    return (
      <Login
        onLogin={() => {
          void query.invalidateQueries({ queryKey: ['me'] });
        }}
      />
    );
  }
  const mediaCards = (items: Media[]) =>
    grid ? (
      <div className="media-grid">
        {items.map((m) => (
          <MediaCard
            key={m.id}
            media={m}
            onOpen={() => openMedia(m.id)}
            selecting={selecting}
            selected={selectedItems.has(itemKey(m))}
            onContextMenu={(event) => itemContext(event, m)}
            onSelect={(shift) => toggleSelection(m, shift)}
            onFavorite={() =>
              act(() =>
                api('/media/' + m.id, { method: 'PATCH', body: JSON.stringify({ favorite: !m.favorite }) }),
              )
            }
          />
        ))}
      </div>
    ) : (
      <div className="media-list">
        {items.map((m) => (
          <div
            className={`media-list-row ${selecting && selectedItems.has(itemKey(m)) ? 'item-selected' : ''}`}
            key={m.id}
          >
            {selecting && (
              <input
                type="checkbox"
                checked={selectedItems.has(itemKey(m))}
                aria-label={m.title + 'を選択'}
                onChange={(e) => toggleSelection(m, (e.nativeEvent as MouseEvent).shiftKey)}
              />
            )}
            <button
              onContextMenu={(event) => itemContext(event, m)}
              onClick={(e) => (selecting ? toggleSelection(m, e.shiftKey) : openMedia(m.id))}
            >
              {m.assets.thumbnail || m.source.thumbnail_url ? (
                <img
                  src={m.assets.thumbnail || m.source.thumbnail_url!}
                  alt=""
                  referrerPolicy="no-referrer"
                />
              ) : (
                <Film size={30} />
              )}
              <strong>{m.title}</strong>
            </button>
            <span>{m.storage_mode === 'REFERENCE' ? m.source.label : time(m.duration_ms)}</span>
            <span>{m.storage_mode === 'REFERENCE' ? 'リンク保存' : `${m.cell_count} Cells`}</span>
            <span>{date(m.created_at)}</span>
            <button
              className="icon-button"
              aria-label={m.favorite ? 'お気に入りを解除' : 'お気に入りに追加'}
              onClick={() =>
                act(() =>
                  api('/media/' + m.id, { method: 'PATCH', body: JSON.stringify({ favorite: !m.favorite }) }),
                )
              }
            >
              <Heart size={17} fill={m.favorite ? 'currentColor' : 'none'} />
            </button>
          </div>
        ))}
      </div>
    );
  const savedCellItems = (items: Cell[]) =>
    items.map((c) => (
      <article
        className={`saved-cell ${selecting && selectedItems.has(itemKey(c)) ? 'item-selected' : ''}`}
        key={c.id}
      >
        {selecting && (
          <label className="item-select">
            <input
              type="checkbox"
              checked={selectedItems.has(itemKey(c))}
              aria-label={c.title + 'を選択'}
              onChange={(e) => toggleSelection(c, (e.nativeEvent as MouseEvent).shiftKey)}
            />
          </label>
        )}
        <button
          className="saved-cell-main"
          onContextMenu={(event) => itemContext(event, c)}
          aria-label={c.title + (selecting ? 'を選択' : 'を開く')}
          aria-pressed={selecting ? selectedItems.has(itemKey(c)) : undefined}
          onClick={(e) => (selecting ? toggleSelection(c, e.shiftKey) : openCell(c))}
        >
          <div>
            {c.thumbnail ? <img src={c.thumbnail} alt="" loading="lazy" /> : <Layers size={24} />}
            <span>
              <Play size={15} />
            </span>
          </div>
          <section>
            <small>{c.media_title}</small>
            <h3>{c.title}</h3>
            <p>
              {time(c.end_ms - c.start_ms)}
              {c.storage_mode === 'REFERENCE' ? ' · リンクの区間' : ''}
            </p>
          </section>
        </button>
        <button className="icon-button" aria-label={`${c.title}を整理`} onClick={() => setOrganize(c)}>
          <FolderPlus size={17} />
        </button>
      </article>
    ));
  const cellCards = (items: Cell[]) => <div className="saved-cells">{savedCellItems(items)}</div>;
  const empty = (kind: string) => (
    <div className="empty-state">
      {kind === 'cells' ? (
        <Layers size={35} />
      ) : kind === 'search' ? (
        <Search size={35} />
      ) : (
        <Film size={35} />
      )}
      <h2>
        {kind === 'cells'
          ? 'まだCellがありません'
          : kind === 'search'
            ? '一致する項目がありません'
            : 'まだ動画がありません'}
      </h2>
      <p>
        {kind === 'cells'
          ? '動画を開いて「Cellを作成」から、好きな区間を保存できます。'
          : kind === 'search'
            ? '別の言葉やタグで検索してみてください。'
            : '動画ファイルやリンクを追加できます。'}
      </p>
      {kind !== 'search' && (
        <button
          className="button primary"
          onClick={() => navigate({ view: kind === 'cells' ? 'library' : 'add' })}
        >
          {kind === 'cells' ? '動画を開く' : '動画を追加'}
        </button>
      )}
    </div>
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        本文へ移動
      </a>
      {mobile && (
        <button
          className="mobile-shade"
          tabIndex={-1}
          aria-label="メニューを閉じる"
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        ref={mobileMenu}
        className={`sidebar ${mobile ? 'open' : ''}`}
        role={mobile ? 'dialog' : undefined}
        aria-modal={mobile || undefined}
        aria-label={mobile ? 'メインメニュー' : undefined}
        onKeyDown={(event) => {
          if (!mobile) return;
          if (event.key === 'Escape') {
            event.preventDefault();
            setMobile(false);
          }
          if (event.key === 'Tab') {
            const controls = Array.from(
              event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]'),
            ).filter((element) => element.getClientRects().length > 0);
            const first = controls[0],
              last = controls.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className="sidebar-brand">
          <Logo />
          <button
            className="icon-button mobile-only"
            onClick={() => setMobile(false)}
            aria-label="メニューを閉じる"
          >
            <X size={20} />
          </button>
        </div>
        <nav aria-label="メインナビゲーション">
          {[
            { id: 'home', label: 'ホーム', icon: Home },
            { id: 'add', label: '追加する', icon: Plus },
            { id: 'library', label: 'ライブラリ', icon: Library },
            { id: 'collections', label: 'Shelf', icon: Folder },
          ].map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id && !shelfId && !collectionId && !search ? 'active' : ''} ${n.id === 'add' ? 'nav-add' : ''}`}
              onClick={() => navigate({ view: n.id })}
            >
              <n.icon size={19} />
              <span>{n.label}</span>
              {n.id === 'library' && <small>{stats.data?.media_count ?? 0}</small>}
            </button>
          ))}
        </nav>
        <div className="shelf-heading">
          <span>自分のShelf</span>
          <button
            className="icon-button"
            aria-label="Shelfを作成"
            onClick={() => setGroupEditor({ kind: 'shelves' })}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="shelf-nav">
          {groups.map((g) => (
            <button
              key={g.id}
              onContextMenu={(event) => shelfContext(event, g)}
              className={`nav-item ${(shelfId || collectionId) === g.id ? 'active' : ''}`}
              onClick={() =>
                navigate({ view: 'library', [g.kind === 'shelves' ? 'shelf' : 'collection']: g.id })
              }
            >
              <span className="shelf-dot" style={{ background: g.color }} />
              <span>{g.name}</span>
              <small>{g.media_count + g.cell_count}</small>
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="storage-meter">
            <div>
              <HardDrive size={15} />
              <span>ライブラリの容量</span>
            </div>
            <progress
              max={10 * 1024 ** 3}
              value={stats.data?.size_bytes ?? 0}
              aria-label="元動画の保存容量"
            />
            <small>
              {bytes(stats.data?.size_bytes ?? 0)} / 10 GB<span>元動画</span>
            </small>
          </div>
        </div>
      </aside>
      <div className="main-shell" inert={mobile}>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              ref={menuTrigger}
              className="icon-button mobile-only"
              aria-label="メニューを開く"
              onClick={() => setMobile(true)}
            >
              <Menu size={22} />
            </button>
            <span>マイライブラリ</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <form
            className="search-box"
            onSubmit={(e) => {
              e.preventDefault();
              if (searchInput.trim()) navigate({ view: 'library', q: searchInput.trim() });
            }}
          >
            <Search size={17} />
            <input
              aria-label="ライブラリを検索"
              placeholder="動画、Cell、タグを検索"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              maxLength={200}
            />
            {searchInput && (
              <button
                type="button"
                className="icon-button"
                aria-label="検索をクリア"
                onClick={() => {
                  setSearchInput('');
                  if (search) navigate({ view: 'library' });
                }}
              >
                <X size={15} />
              </button>
            )}
          </form>
          <div className="topbar-tools">
            <button
              className={`icon-button topbar-icon ${running.length ? 'processing' : ''}`}
              onClick={() => setProgressOpen(true)}
              aria-label="処理の進捗を開く"
            >
              {running.length ? <Loader2 className="spin" size={19} /> : <Clock size={19} />}
            </button>
            <AccountMenu
              user={me.data}
              onSettings={() => navigate({ view: 'settings' })}
              onLogout={() => {
                void act(async () => {
                  await api('/auth/logout', { method: 'POST' });
                  query.clear();
                  window.location.assign(new URL('/', window.location.origin).href);
                });
              }}
            />
          </div>
        </header>
        <main id="main-content" className="main-content">
          {focusedGroup?.header_url && (
            <ShelfHeaderImage
              className="shelf-page-header"
              group={focusedGroup}
              alt={`${focusedGroup.name}のヘッダー`}
            />
          )}
          <div className={`page-heading ${view === 'home' && !search ? 'home-page-heading' : ''}`}>
            <div>
              <h1>{title}</h1>
              {focusedGroup?.description && !search && <p>{focusedGroup.description}</p>}
            </div>
            <div className="heading-actions">
              {(view === 'library' || view === 'collections') && !search && (
                <LinkSharing
                  scope={{
                    kind: focusedGroup ? (shelfId ? 'shelves' : 'collections') : 'library',
                    ...(focusedGroup ? { group_id: focusedGroup.id } : {}),
                    ...(selectedItems.size
                      ? {
                          media_ids: [...selectedItems.values()]
                            .filter((item) => !('media_id' in item))
                            .map((item) => item.id),
                          cell_ids: [...selectedItems.values()]
                            .filter((item) => 'media_id' in item)
                            .map((item) => item.id),
                        }
                      : {}),
                  }}
                  label={
                    selectedItems.size
                      ? '選んだ項目を共有'
                      : focusedGroup
                        ? 'このShelfを共有'
                        : 'リンク集を共有'
                  }
                  onChanged={refresh}
                  notify={setToast}
                />
              )}
              {focusedGroup && (
                <>
                  <button
                    className="icon-button"
                    aria-label="整理先を編集"
                    onClick={() =>
                      setGroupEditor({ kind: shelfId ? 'shelves' : 'collections', group: focusedGroup })
                    }
                  >
                    <Pencil size={18} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="整理先を削除"
                    onClick={() =>
                      setGroupDelete({ kind: shelfId ? 'shelves' : 'collections', group: focusedGroup })
                    }
                  >
                    <Trash2 size={18} />
                  </button>
                </>
              )}
              {view !== 'add' && view !== 'settings' && (
                <button
                  className="button primary"
                  onClick={() =>
                    view === 'collections' && !collectionId
                      ? setGroupEditor({ kind: 'shelves' })
                      : navigate({
                          view: 'add',
                          ...(shelfId ? { shelf: shelfId } : {}),
                          ...(collectionId ? { collection: collectionId } : {}),
                        })
                  }
                >
                  <Plus size={17} />
                  {view === 'collections' && !collectionId ? 'Shelfを作成' : '動画を追加'}
                </button>
              )}
            </div>
          </div>
          {error && !groupEditor && !organize && (
            <div className="error-message dismissible" role="alert">
              {error}
              <button aria-label="エラーを閉じる" onClick={() => setError('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {view === 'home' && !search && (
            <>
              <section className="home-intro">
                <div className="home-intro-copy">
                  <h1>ライブラリ</h1>
                  <div className="home-library-counts" aria-label="ライブラリの件数">
                    <button onClick={() => navigate({ view: 'library', tab: 'videos' })}>
                      <strong>{stats.data?.media_count ?? '—'}</strong>
                      <span>動画</span>
                    </button>
                    <button onClick={() => navigate({ view: 'library', tab: 'cells' })}>
                      <strong>{stats.data?.cell_count ?? '—'}</strong>
                      <span>Cells</span>
                    </button>
                    <button onClick={() => navigate({ view: 'collections' })}>
                      <strong>{stats.data?.shelf_count ?? '—'}</strong>
                      <span>Shelf</span>
                    </button>
                  </div>
                  <div className="home-intro-actions">
                    <button className="button primary" onClick={() => navigate({ view: 'add' })}>
                      <Plus size={16} /> 動画を追加
                    </button>
                    {!!stats.data?.media_count && (
                      <button className="text-button" onClick={() => navigate({ view: 'library' })}>
                        ライブラリを開く <ChevronRight size={15} />
                      </button>
                    )}
                  </div>
                </div>
                <HomeSculpture />
              </section>
              <ContentRail
                title="最近追加した動画"
                more={
                  <button className="text-button" onClick={() => navigate({ view: 'library' })}>
                    すべて見る <ChevronRight size={15} />
                  </button>
                }
              >
                {media.isPending ? (
                  <SkeletonCards />
                ) : media.isError ? (
                  <LoadError message={media.error.message} retry={() => media.refetch()} />
                ) : media.data?.items.length ? (
                  media.data.items.map((m) => (
                    <MediaCard
                      key={m.id}
                      media={m}
                      onContextMenu={(event) => itemContext(event, m)}
                      onOpen={() => openMedia(m.id)}
                      onFavorite={() =>
                        act(() =>
                          api('/media/' + m.id, {
                            method: 'PATCH',
                            body: JSON.stringify({ favorite: !m.favorite }),
                          }),
                        )
                      }
                    />
                  ))
                ) : (
                  <div className="welcome-empty">
                    <Film size={27} />
                    <div>
                      <h3>動画を追加</h3>
                      <p>リンクや動画ファイルを追加できます。</p>
                    </div>
                    <button className="text-button" onClick={() => navigate({ view: 'add' })}>
                      動画を追加 <Plus size={16} />
                    </button>
                  </div>
                )}
              </ContentRail>
              <ContentRail
                title="保存したCells"
                kind="cells"
                more={
                  <button className="text-button" onClick={() => navigate({ view: 'library', tab: 'cells' })}>
                    すべて見る <ChevronRight size={15} />
                  </button>
                }
              >
                {cells.data?.items.length ? (
                  savedCellItems(cells.data.items.slice(0, 12))
                ) : (
                  <div className="moment-tip">
                    <BookmarkPlus size={24} />
                    <div>
                      <h3>区間を保存</h3>
                      <p>動画を開き、開始と終了を指定してCellを作成できます。</p>
                    </div>
                  </div>
                )}
              </ContentRail>
              <ContentRail
                title="自分のShelf"
                kind="shelves"
                more={
                  <button className="text-button" onClick={() => setGroupEditor({ kind: 'shelves' })}>
                    <Plus size={15} /> 作成
                  </button>
                }
              >
                {groups.length ? (
                  groups.slice(0, 12).map((group) => (
                    <button
                      className="home-shelf"
                      onContextMenu={(event) => shelfContext(event, group)}
                      key={group.id}
                      onClick={() =>
                        navigate({
                          view: 'library',
                          [group.kind === 'shelves' ? 'shelf' : 'collection']: group.id,
                        })
                      }
                    >
                      {group.header_url ? (
                        <ShelfHeaderImage group={group} />
                      ) : (
                        <div className="shelf-placeholder" style={{ background: group.color + '0c' }}>
                          <Folder size={34} style={{ color: group.color }} />
                        </div>
                      )}
                      <div className="home-shelf-caption">
                        <span>
                          <strong>{group.name}</strong>
                          <small>
                            {group.media_count}本 · {group.cell_count} Cells
                          </small>
                        </span>
                        <ChevronRight size={16} />
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="moment-tip">
                    <Folder size={24} />
                    <p>好きなテーマで、動画とCellをまとめられます。</p>
                  </div>
                )}
              </ContentRail>
            </>
          )}
          {view === 'add' && !search && (
            <AddMedia
              onComplete={refresh}
              onOpen={openMedia}
              groups={groups}
              destination={addDestination}
              onDestinationChange={setAddDestination}
              onCreateShelf={() => setGroupEditor({ kind: 'shelves' })}
            />
          )}
          {(view === 'library' || (view === 'collections' && !!collectionId)) && !search && (
            <>
              <div className="library-toolbar">
                <div className="segmented" aria-label="表示する項目">
                  <button
                    className={mode === 'videos' ? 'active' : ''}
                    onClick={() =>
                      navigate({
                        view: 'library',
                        ...(shelfId ? { shelf: shelfId } : {}),
                        ...(collectionId ? { collection: collectionId } : {}),
                        tab: 'videos',
                      })
                    }
                  >
                    <Film size={16} />
                    動画 <span>{media.data?.total ?? 0}</span>
                  </button>
                  {
                    <button
                      className={mode === 'cells' ? 'active' : ''}
                      onClick={() =>
                        navigate({
                          view: 'library',
                          ...(collectionId ? { collection: collectionId } : {}),
                          ...(shelfId ? { shelf: shelfId } : {}),
                          tab: 'cells',
                        })
                      }
                    >
                      <Layers size={16} />
                      Cells <span>{cells.data?.total ?? 0}</span>
                    </button>
                  }
                </div>
                <div className="filter-actions">
                  <button
                    ref={selectionTrigger}
                    className="button secondary compact"
                    aria-pressed={selecting}
                    aria-keyshortcuts={selecting ? 'Escape' : undefined}
                    onClick={() => {
                      if (selecting) endSelection();
                      else {
                        setSelectionMode(true);
                        setSelectionAnchor(null);
                        setSelectedItems(new Map());
                      }
                    }}
                  >
                    {selecting ? '選択を終了' : '選択'}
                  </button>
                  {mode !== 'cells' && (
                    <>
                      <button
                        className={`button compact ${favorite ? 'selected' : 'secondary'}`}
                        aria-pressed={favorite}
                        onClick={() => {
                          setFavorite(!favorite);
                          setOffset(0);
                        }}
                      >
                        <Heart size={15} />
                        お気に入り
                      </button>
                      <select
                        aria-label="並び順"
                        value={sort}
                        onChange={(e) => {
                          setSort(e.target.value);
                          setOffset(0);
                        }}
                      >
                        <option value="newest">新しい順</option>
                        <option value="oldest">古い順</option>
                        <option value="title">タイトル順</option>
                      </select>
                      <div className="view-toggle">
                        <button
                          className={grid ? 'active' : ''}
                          onClick={() => setGrid(true)}
                          aria-label="グリッド表示"
                          aria-pressed={grid}
                        >
                          <LayoutGrid size={17} />
                        </button>
                        <button
                          className={!grid ? 'active' : ''}
                          onClick={() => setGrid(false)}
                          aria-label="リスト表示"
                          aria-pressed={!grid}
                        >
                          <List size={18} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
              {selecting && (
                <div className="selection-toolbar" role="region" aria-label="選択した項目を整理">
                  <strong>{selectedItems.size}件を選択</strong>
                  <button
                    className="text-button"
                    onClick={() => {
                      const displayed: (Media | Cell)[] =
                        mode === 'cells' ? (cells.data?.items ?? []) : (media.data?.items ?? []);
                      const next = new Map(selectedItems);
                      for (const item of displayed) {
                        if (next.size >= 100 && !next.has(itemKey(item))) break;
                        next.set(itemKey(item), item);
                      }
                      setSelectedItems(next);
                    }}
                  >
                    表示中をすべて選択
                  </button>
                  <button
                    className="text-button"
                    disabled={!selectedItems.size}
                    onClick={() => {
                      setSelectedItems(new Map());
                      setSelectionAnchor(null);
                    }}
                  >
                    チェックをすべて外す
                  </button>
                  <button
                    className="button primary compact"
                    disabled={!selectedItems.size}
                    onClick={() => setBatchOpen(true)}
                  >
                    <FolderPlus size={16} />
                    Shelfに追加
                  </button>
                  <button
                    className="button secondary compact danger-text"
                    disabled={!selectedItems.size}
                    onClick={() => setBatchDeleteOpen(true)}
                  >
                    <Trash2 size={16} />
                    削除
                  </button>
                  <button
                    className="button secondary compact"
                    onClick={endSelection}
                    aria-keyshortcuts="Escape"
                  >
                    <X size={16} />
                    選択モードを終了
                  </button>
                </div>
              )}
              {mode === 'cells' ? (
                cells.isPending ? (
                  <SkeletonCards />
                ) : cells.isError ? (
                  <LoadError message={cells.error.message} retry={() => cells.refetch()} />
                ) : cells.data?.items.length ? (
                  cellCards(cells.data.items)
                ) : (
                  empty('cells')
                )
              ) : media.isPending ? (
                <SkeletonCards />
              ) : media.isError ? (
                <LoadError message={media.error.message} retry={() => media.refetch()} />
              ) : media.data?.items.length ? (
                mediaCards(media.data.items)
              ) : (
                empty('videos')
              )}
              <Pagination
                offset={offset}
                total={(mode === 'cells' ? cells.data : media.data)?.total ?? 0}
                step={24}
                onChange={setOffset}
              />
            </>
          )}
          {view === 'collections' && !collectionId && !search && (
            <div className="collection-grid">
              {groups.map((g) => (
                <article key={g.id} className="collection-card">
                  <button
                    onContextMenu={(event) => shelfContext(event, g)}
                    onClick={() =>
                      navigate({ view: 'library', [g.kind === 'shelves' ? 'shelf' : 'collection']: g.id })
                    }
                  >
                    <div
                      className="collection-visual"
                      style={{ '--group-color': g.color } as React.CSSProperties}
                    >
                      {g.header_url ? (
                        <ShelfHeaderImage group={g} />
                      ) : (
                        <>
                          <Folder size={55} strokeWidth={1.2} />
                          <span>{g.media_count + g.cell_count}</span>
                        </>
                      )}
                    </div>
                    <h2>{g.name}</h2>
                    <p>{g.description || '動画とCellをまとめる場所'}</p>
                    <small>
                      {g.media_count} 動画 <span>·</span> {g.cell_count} Cells
                    </small>
                  </button>
                  <button
                    className="icon-button collection-edit"
                    aria-label={`${g.name}を編集`}
                    onClick={() => setGroupEditor({ kind: g.kind, group: g })}
                  >
                    <Pencil size={16} />
                  </button>
                </article>
              ))}
              <button className="collection-new" onClick={() => setGroupEditor({ kind: 'shelves' })}>
                <span>
                  <Plus size={25} />
                </span>
                <h3>新しいShelf</h3>
                <p>テーマや気分でまとめよう</p>
              </button>
            </div>
          )}
          {search && (
            <>
              {results.isPending ? (
                <SkeletonCards />
              ) : results.isError ? (
                <LoadError message={results.error.message} retry={() => results.refetch()} />
              ) : results.data?.total === 0 ? (
                empty('search')
              ) : (
                <>
                  <div className="search-summary">{results.data?.total}件見つかりました</div>
                  {!!results.data?.media.length && (
                    <>
                      <div className="section-heading">
                        <h2>
                          動画 <span>{results.data.counts.media}</span>
                        </h2>
                      </div>
                      {mediaCards(results.data.media)}
                    </>
                  )}
                  {!!results.data?.cells.length && (
                    <>
                      <div className="section-heading more-space">
                        <h2>
                          Cells <span>{results.data.counts.cells}</span>
                        </h2>
                      </div>
                      {cellCards(results.data.cells)}
                    </>
                  )}
                  {[...(results.data?.transcripts ?? []), ...(results.data?.events ?? [])].map((r) => (
                    <button
                      className="search-moment"
                      key={r.id}
                      onClick={() => openMedia(r.media_id!, r.start_ms, r.end_ms)}
                    >
                      <Play size={18} />
                      <div>
                        <strong>{'text' in r ? r.text : r.label}</strong>
                        <span>
                          {r.media_title} · {time(r.start_ms)}
                        </span>
                      </div>
                    </button>
                  ))}
                  <Pagination
                    offset={offset}
                    total={Math.max(0, ...Object.values(results.data?.counts ?? {}))}
                    step={20}
                    onChange={setOffset}
                  />
                </>
              )}
            </>
          )}
          {view === 'settings' && !search && (
            <SettingsView
              user={me.data}
              stats={stats.data}
              notify={setToast}
              onLogout={async () => {
                await api('/auth/logout', { method: 'POST' });
                query.clear();
                window.location.assign(new URL('/', window.location.origin).href);
              }}
            />
          )}
          <footer className="page-footer">
            <span>Lumvia</span>
            <span className="private-label">
              <ShieldCheck size={13} />
              所有者だけが利用できます
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {toast}
          <button aria-label="通知を閉じる" onClick={() => setToast('')}>
            <X size={15} />
          </button>
        </div>
      )}
      {context && <ItemContextMenu {...context} onClose={closeContext} />}
      {mediaId && !cellId && (
        <MediaDetail
          key={mediaId}
          id={mediaId}
          initialTime={Number(params.get('t') || 0)}
          initialEnd={params.has('end') ? Number(params.get('end')) : undefined}
          onClose={closeMedia}
          onChanged={refresh}
          notify={setToast}
          onOrganize={setOrganize}
          onOpenCell={openCell}
        />
      )}
      {cellId && (
        <CellDetail
          key={cellId}
          id={cellId}
          onClose={closeMedia}
          onChanged={refresh}
          notify={setToast}
          onOrganize={setOrganize}
          onOpenMedia={openMedia}
        />
      )}
      {batchOpen && (
        <BatchOrganize
          items={[...selectedItems.values()]}
          shelves={shelves.data?.items ?? []}
          collections={collections.data?.items ?? []}
          onClose={() => setBatchOpen(false)}
          onChanged={() => {
            refresh();
            setSelectedItems(new Map());
            setSelectionMode(false);
          }}
          notify={setToast}
        />
      )}
      {batchDeleteOpen && (
        <BatchDelete
          items={[...selectedItems.values()]}
          onClose={() => setBatchDeleteOpen(false)}
          onChanged={() => {
            refresh();
            setSelectedItems(new Map());
            setSelectionMode(false);
          }}
          notify={setToast}
        />
      )}
      <Modal
        open={!!groupEditor}
        onClose={() => {
          setGroupEditor(null);
          setError('');
        }}
        title={`Shelfを${groupEditor?.group ? '編集' : '作成'}`}
        description="動画とCellを整理する、自分だけの棚を作ります。"
      >
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!groupEditor) return;
            const data = new FormData(e.currentTarget);
            if (
              await act(
                () =>
                  api<Group>('/' + groupEditor.kind + (groupEditor.group ? '/' + groupEditor.group.id : ''), {
                    method: groupEditor.group ? 'PATCH' : 'POST',
                    body: JSON.stringify(Object.fromEntries(data)),
                  }).then((g) => {
                    if (!groupEditor.group && view === 'add')
                      setAddDestination(`${groupEditor.kind}:${g.id}`);
                    return g;
                  }),
                '保存しました',
              )
            )
              setGroupEditor(null);
          }}
        >
          <label>
            名前
            <input
              name="name"
              key={groupEditor?.group?.id ?? 'new'}
              defaultValue={groupEditor?.group?.name ?? ''}
              required
              maxLength={100}
              placeholder="例：旅の記録"
            />
          </label>
          <label>
            説明
            <textarea
              name="description"
              defaultValue={groupEditor?.group?.description ?? ''}
              maxLength={500}
              rows={3}
              placeholder="どんな動画を集めますか？"
            />
          </label>
          <ColorPicker key={groupEditor?.group?.id ?? 'new'} initial={groupEditor?.group?.color} />
          {groupEditor?.group && (
            <ShelfHeaderPicker
              group={groupEditor.group}
              kind={groupEditor.kind}
              onChanged={(group) => {
                setGroupEditor((current) =>
                  current?.group?.id === group.id ? { ...current, group } : current,
                );
                refresh();
              }}
            />
          )}
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            {groupEditor?.group && (
              <button
                type="button"
                className="text-button danger-text"
                onClick={() => {
                  setGroupDelete({ kind: groupEditor.kind, group: groupEditor.group! });
                  setGroupEditor(null);
                }}
              >
                削除
              </button>
            )}
            <button className="button primary" disabled={busy}>
              {busy ? '保存中…' : '保存する'}
            </button>
          </div>
        </form>
      </Modal>
      <Confirm
        open={!!groupDelete}
        onClose={() => setGroupDelete(null)}
        title={`${groupDelete?.group.name ?? '整理先'}を削除しますか？`}
        description="この整理先だけを削除します。中の動画やCellはライブラリに残ります。"
        pending={busy}
        onConfirm={async () => {
          if (
            groupDelete &&
            (await act(
              () => api(`/${groupDelete.kind}/${groupDelete.group.id}`, { method: 'DELETE' }),
              '整理先を削除しました',
            ))
          ) {
            setGroupDelete(null);
            navigate({ view: 'library' });
          }
        }}
      />
      {organize && (
        <Organize
          item={organize}
          shelves={shelves.data?.items ?? []}
          collections={collections.data?.items ?? []}
          onClose={() => setOrganize(null)}
          onChanged={refresh}
          notify={setToast}
        />
      )}
      <Modal
        open={progressOpen}
        onClose={() => setProgressOpen(false)}
        title="処理の進捗"
        description="画面を閉じても、動画の準備や解析は続きます。"
      >
        <div className="jobs-list">
          {jobs.isError ? (
            <LoadError message={jobs.error.message} retry={() => jobs.refetch()} />
          ) : jobs.data?.items.length ? (
            jobs.data.items.map((j) => (
              <div className="job-card" key={j.id}>
                <div className="job-title">
                  {activeJob(j) ? (
                    <Loader2 size={19} className="spin" />
                  ) : j.state === 'COMPLETED' ? (
                    <CheckCircle2 size={19} className="success" />
                  ) : (
                    <AlertCircle size={19} className="muted" />
                  )}
                  <div>
                    <strong>{j.media_title}</strong>
                    <span>
                      {j.kind === 'ingest' ? '動画の準備' : j.kind === 'scenes' ? 'シーン解析' : '過去の処理'}{' '}
                      · {jobLabel[j.state]}
                    </span>
                  </div>
                </div>
                {activeJob(j) && (
                  <progress value={j.progress} max={100} aria-label={`${j.media_title}の進捗`} />
                )}
                <div className="job-actions">
                  {j.error_message && <p>{j.error_message}</p>}
                  {activeJob(j) && j.state !== 'CANCEL_REQUESTED' && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        act(() => api(`/jobs/${j.id}/cancel`, { method: 'POST' }), '停止をリクエストしました')
                      }
                    >
                      キャンセル
                    </button>
                  )}
                  {['FAILED', 'CANCELLED', 'TIMED_OUT'].includes(j.state) && j.attempt < 3 && (
                    <button
                      className="button compact secondary"
                      disabled={busy}
                      onClick={() =>
                        act(() => api(`/jobs/${j.id}/retry`, { method: 'POST' }), '再試行を開始しました')
                      }
                    >
                      <RefreshCw size={14} />
                      再試行
                    </button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="inline-empty">
              <Clock size={30} />
              <p>処理中の動画はありません。</p>
            </div>
          )}
        </div>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
      </Modal>
    </div>
  );
}
function SkeletonCards() {
  return (
    <div className="media-grid" aria-label="読み込み中">
      {[1, 2, 3, 4].map((i) => (
        <div className="skeleton skeleton-card" key={i} />
      ))}
    </div>
  );
}
function LoadError({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="error-message" role="alert">
      {message}
      <button className="button secondary compact" onClick={retry}>
        再試行
      </button>
    </div>
  );
}
function Pagination({
  offset,
  total,
  step,
  onChange,
}: {
  offset: number;
  total: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return total > step ? (
    <div className="pagination">
      <button
        className="button secondary"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - step))}
      >
        前へ
      </button>
      <span>
        {offset + 1}–{Math.min(offset + step, total)} / {total}
      </span>
      <button
        className="button secondary"
        disabled={offset + step >= total}
        onClick={() => onChange(offset + step)}
      >
        次へ
      </button>
    </div>
  ) : null;
}
