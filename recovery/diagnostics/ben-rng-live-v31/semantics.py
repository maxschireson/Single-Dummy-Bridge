def semantics(record):
    # Capture every root and audit action, score, seed, assignment and auction.
    # BEN has no gaps/audits; self-play gap CPU caps can change capture volume,
    # so separately compare the complete root + tie-audit trajectory.
    episodes = {}
    for key, episode in record['unique_tables'].items():
        tables = []
        for table in episode['tables']:
            if table.get('node', '').startswith('gap'):
                continue
            tables.append({k: table.get(k) for k in ('node', 'depth', 'status', 'ns_score', 'declarer_tricks')})
            tables[-1]['actions'] = [{k: action.get(k) for k in
                ('ply', 'seat', 'controller', 'player', 'card', 'behavior_probabilities', 'selected_probability', 'selected_pimc_gap')}
                for action in table['actions']]
        episodes[key] = dict(board=episode['board'], seed=episode.get('seed'),
            assignments=episode.get('assignments'), tables=tables)
    return dict(index=record['index'], family=record['family'], pair=record['pair'],
        versions=record['versions'], regimes=record['regimes'], episodes=episodes)


