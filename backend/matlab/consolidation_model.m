function [tv, uav, t_years, settlement, tv_emp, uav_emp] = consolidation_model(ks, mv, th, drainage, u0)
%CONSOLIDATION_MODEL  Parameterised version of final_analytical.m (Pushkar Nath Chaurasia, 23-01-2025).
%
%   Same method as the original script (Terzaghi series solution of the pore
%   pressure u(z,t), Uav from the area under the u-z curve, empirical Tv(U)
%   curve), with these differences so it can be driven by a web app:
%     * inputs are arguments instead of hard-coded values
%     * the time grid is log-spaced from 0.1 s to 100 years (the original only
%       ran 50 s), so the curve reaches Uav = 1
%     * vectorised (same numbers, much faster); no figures
%     * settlement(t) = Uav(t) * mv * u0 * th   [mm]
%     * drainage 'single' uses the full drainage path d = th and a series
%       period H = 2*d. For 'double' this is identical to the original script.
%
%   Inputs
%     ks        permeability                      [m/s]
%     mv        coeff. of volume compressibility  [m^2/kN]
%     th        soil layer thickness              [m]
%     drainage  'double' or 'single'
%     u0        initial pore pressure / load      [kN/m^2]

    yw = 9.81;                         % kN/m^3
    cv = ks / (yw * mv);               % m^2/s

    if strcmpi(drainage, 'double')
        d = th / 2;
    else
        d = th;
    end
    H = 2 * d;                         % period of the sine series

    nn = 100;                          % number of elements
    z  = linspace(0, th, nn + 1)';     % depth nodes (column)
    N  = 0:1000;                       % series terms (row)
    k  = (2 * N + 1);

    SEC_PER_YEAR = 365.25 * 24 * 3600;
    time = [0, logspace(-1, log10(100 * SEC_PER_YEAR), 600)];   % seconds
    nt = numel(time);

    S = sin(z * (k * pi / H));         % (nn+1) x numel(N)
    coef = (4 / pi) * u0 ./ k;         % 1 x numel(N)
    rate = ((k * pi / H) .^ 2) * cv;   % 1 x numel(N)

    uav = zeros(1, nt);
    a0 = u0 * th;
    for t = 2:nt
        u = S * (coef .* exp(-rate * time(t)))';     % column of pore pressures
        uav(t) = 1 - trapz(z, u) / a0;
    end
    uav = min(max(uav, 0), 1);

    tv = cv .* time ./ (d ^ 2);

    t_years = time / SEC_PER_YEAR;
    settlement = uav * mv * u0 * th * 1000;          % mm

    % empirical Tv for given Uav (from the original script)
    uav_emp = 0.01:0.01:0.99;
    tv_emp = zeros(size(uav_emp));
    for ii = 1:numel(uav_emp)
        if uav_emp(ii) <= 0.6
            tv_emp(ii) = (pi / 4) * uav_emp(ii) ^ 2;
        else
            tv_emp(ii) = -0.085 - 0.933 * log10(1 - uav_emp(ii));
        end
    end
end

