function run_case(ks, mv, th, drainage, u0, outfile)
%RUN_CASE  Called by the web backend:
%     run_case(6.28e-6, 5.6e-6, 10, 'double', 100, '/tmp/xyz/result.json')
%   Runs consolidation_model and writes the result as JSON.

    drainage = char(drainage);
    [tv, uav, t_hours, settlement, tv_t, uav_t] = consolidation_model(ks, mv, th, drainage, u0);

    out = struct('tv', tv(:)', 'uav', uav(:)', ...
                 't_hours', t_hours(:)', 'settlement', settlement(:)', ...
                 'tv_t', tv_t(:)', 'uav_t', uav_t(:)');

    fid = fopen(outfile, 'w');
    if fid < 0
        error('run_case:io', 'Cannot open output file %s', outfile);
    end
    fwrite(fid, jsonencode(out), 'char');
    fclose(fid);
end
