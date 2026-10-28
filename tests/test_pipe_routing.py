"""The visible piping must be continuous, orthogonal and circuit-isolated."""
import math
from thermalloop.config_loader import load_config
from thermalloop.simulation import run_simulation


def test_every_shared_node_has_one_physical_connection_point():
    for circuit in load_config()['network']['circuits'].values():
        positions = {}
        for pipe in circuit['segments']:
            for node, point in [(pipe['from'], pipe['points'][0]), (pipe['to'], pipe['points'][-1])]:
                assert node in circuit['nodes']
                assert positions.setdefault(node, point) == point, (pipe['id'], node)
            for a, b in zip(pipe['points'], pipe['points'][1:]):
                assert sum(x != y for x, y in zip(a, b)) == 1, pipe['id']
            length = sum(math.dist(a, b) for a, b in zip(pipe['points'], pipe['points'][1:]))
            assert abs(length - pipe['length_m']) < .001


def test_primary_and_secondary_use_distinct_heat_exchanger_ports():
    cfg = load_config()
    endpoints = {}
    for name, circuit in cfg['network']['circuits'].items():
        endpoints[name] = {tuple(p) for s in circuit['segments'] for p in [s['points'][0], s['points'][-1]]}
    assert endpoints['primary'].isdisjoint(endpoints['secondary'])


def test_gpu_branches_have_one_riser_and_distinct_hot_and_cold_manifolds():
    pipes = {p['id']: p for p in load_config()['network']['circuits']['primary']['segments']}
    for f in ['f1', 'f2', 'f3']:
        supply = pipes[f'pipe_pri_riser_{f}_001']
        pickup = pipes[f'pipe_pri_floor_transfer_{f}_001']
        returning = pipes[f'pipe_pri_return_{f}_001']
        assert supply['points'][0][0] == 14.8
        assert returning['points'][-1][0] == 16.4
        assert supply['to'] == pickup['from']
        assert pickup['to'] == returning['from']
        assert supply['points'][-1] == pickup['points'][0]
        assert pickup['points'][-1] == returning['points'][0]


def test_disabled_cooler_and_inactive_storage_have_no_flow_arrows():
    run = run_simulation({'duration_s': 3600, 'timestep_s': 600, 'aux_rejection_enabled': False})
    for step in run['series']:
        pipes = step['pipe_states']
        assert pipes['pipe_pri_aux_reject_001']['mass_flow_kg_s'] == 0
        assert pipes['pipe_pri_aux_return_001']['mass_flow_kg_s'] == 0
        assert pipes['pipe_pri_aux_bypass_001']['mass_flow_kg_s'] == step['primary_mass_flow_kg_s']
        if step['buffer_charge_W'] == 0:
            assert pipes['pipe_buffer_charge_001']['mass_flow_kg_s'] == 0
        if step['buffer_discharge_W'] == 0:
            assert pipes['pipe_buffer_discharge_001']['mass_flow_kg_s'] == 0
        assert pipes['pipe_treatment_feed_001']['temperature_C'] == step['secondary_return_C']


def test_tanks_have_distinct_inlet_and_outlet_ports():
    pipes = {p['id']: p for p in load_config()['network']['circuits']['secondary']['segments']}
    for inlet, outlet in [('pipe_buffer_charge_001', 'pipe_buffer_discharge_001'),
                          ('pipe_treatment_feed_001', 'pipe_treatment_return_001')]:
        assert pipes[inlet]['to'] != pipes[outlet]['from']
        assert pipes[inlet]['points'][-1] != pipes[outlet]['points'][0]


def test_buried_pair_runs_inside_the_utility_corridor():
    cfg = load_config()
    corridor = cfg['geometry']['utility_corridor']
    x = sum(p[0] for p in corridor['path']) / 2
    y = corridor['path'][0][1]
    pipes = {p['id']: p for p in cfg['network']['circuits']['secondary']['segments']}
    for id in ['pipe_buried_supply_001', 'pipe_buried_return_001']:
        crossings = [a for a, b in zip(pipes[id]['points'], pipes[id]['points'][1:])
                     if min(a[0], b[0]) < x < max(a[0], b[0])]
        assert crossings, id
        assert all(abs(p[1] - y) < corridor['width_y'] / 2
                   and corridor['z'][0] < p[2] < corridor['z'][1]
                   for p in crossings)
