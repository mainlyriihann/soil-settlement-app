function [tv, uav_curve, t_hours, settlement, tv_t, uav_t] = consolidation_model(ks, mv, th, drainage, u0)
% By Pushkar Nath Chaurasia, date 23-01-2025
% solving consolidation equation using analytical solution


yw=9.81;   
if strcmpi(drainage, 'double')
    d=th/2; % th/2 for double drainage; th for single drainage
else
    d=th;
end
H=2*d;      % WEB APP: 2*d (= th for double drainage, 2*th for single drainage)
% u0=100;  %initial value of pore pressure          % WEB APP: input
cv=ks/(yw*mv);
nn=100; % No. of element
deltaz=th/(nn);
z=linspace(0,th,nn+1);

% WEB APP: replaces  deltat=0.1; ftime=500*deltat;  (linear 0 .. 50 s)
SEC_PER_HOUR = 3600;
MAX_HOURS = 876600;
tv_grid = logspace(-4, log10(3), 200);                           % for the Uav-Tv curve
time_all = [0, tv_grid*d^2/cv, logspace(-1, log10(MAX_HOURS*SEC_PER_HOUR), 300)];
time_all = unique(time_all);                                     % sorted, starts at 0
ntime = numel(time_all);

u=zeros(nn+1,ntime);
time(1)=0;
t=1;
u(1:nn+1,1)=u0;
 for v=2:ntime                                                   % WEB APP: was  for v=deltat:deltat:ftime

         dez=0;
    for i=1:nn+1
        for N=0:1:1000
            u(i,t+1)=u(i,t+1)+((4/pi)*u0*((1/(2*N+1))*(sin(((2*N+1)*pi*dez)/H))*exp(-(((2*N+1)*pi/H)^2)*cv*time_all(t+1))));   % WEB APP: time(t) -> time_all(t+1)
        end
        dez=dez+deltaz;
    end

     time(t+1)=time_all(t+1);                                    % WEB APP: was  time(t)+deltat
     t=t+1;
 end
%%

 %%
 a(1)=u0*th;
 for i=2:1:t
 a(i)=polyarea([0; u(:,i); 0],[0; z'; th]);
 uav(i)=1-(a(i)/a(1));
 end
 uav(1)=0;

tv1=cv.*(time)./(d^2);


%% calculation of tv for different u
uav2=0.01:0.01:0.99;

for ii=1:1:length(uav2)
if uav2(ii)<=0.6%
    tv2(ii)=(pi/4).*(uav2(ii)^2);
else
     tv2(ii)=1.7781-0.933*log10(100-(uav2(ii)*100));
     tv2(ii)=-0.085-0.933*log10(1-(uav2(ii)));
end
end


% ---------------------------------------------------------------- WEB APP: outputs
% Uav-Tv curve (what figure(3) plotted): only the range Tv <= 3
keep = tv1 <= 3;
tv = tv1(keep);
uav_curve = uav(keep);

% settlement vs time (0 .. 876600 hours)
keep = time <= MAX_HOURS*SEC_PER_HOUR*(1+1e-9);
t_hours = time(keep) / SEC_PER_HOUR;
settlement = uav(keep) * mv * u0 * th * 1000;                    % mm
tv_t = tv1(keep);                                                % Tv and Uav at those same times
uav_t = uav(keep);                                               % (lets the page mark the chosen time on the Uav-Tv curve)
end
