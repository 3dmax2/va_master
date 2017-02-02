var React = require('react');
var connect = require('react-redux').connect;
var Network = require('../network');
var Bootstrap = require('react-bootstrap');
var ReactDOM = require('react-dom');

var Appp = React.createClass({
    getInitialState: function () {
        return {hosts: []};
    },

    getHostInfo: function() {
        var data = {hosts: []};
        Network.post('/api/hosts/info', this.props.auth.token, data).done(function(data) {
            this.setState({hosts: data});
        }.bind(this));
    },

    componentDidMount: function () {
        this.getHostInfo();
    },

    componentWillUnmount: function () {
        this.props.dispatch({type: 'RESET_APP'});
    },

    btn_clicked: function(hostname, host, evtKey){
        var me = this;
        var data = {hostname: host, instance_name: hostname, action: evtKey};
        Network.post('/api/apps/action', this.props.auth.token, data).done(function(d) {
            Network.post('/api/hosts/info', me.props.auth.token, {hosts: []}).done(function(data) {
                me.setState({hosts: data});
            });
        });
    },

    render: function () {
        var app_rows = [];
        for(var i = 0; i < this.state.hosts.length; i++){
            // hostname = this.state.hosts[i].hostname;
            var rows = this.state.hosts[i].instances.map(function(app) {
                ipaddr = app.ip;
                if(Array.isArray(ipaddr)){
                    if(ipaddr.length > 0){
                        var ips = "";
                        for(j=0; j<ipaddr.length; j++){
                            ips += ipaddr[j].addr + ", ";
                        }
                        ipaddr = ips.slice(0, -2);
                    }else{
                        ipaddr = "";
                    }
                }
                return (
                    <tr key={app.hostname}>
                        <td>{app.hostname}</td>
                        <td>{ipaddr}</td>
                        <td>{app.size}</td>
                        <td>{app.status}</td>
                        <td>{app.host}</td>
                        <td>
                            <Bootstrap.DropdownButton bsStyle='primary' title="Choose" onSelect = {this.btn_clicked.bind(this, app.hostname, app.host)}>
                                <Bootstrap.MenuItem eventKey="reboot">Reboot</Bootstrap.MenuItem>
                                <Bootstrap.MenuItem eventKey="delete">Delete</Bootstrap.MenuItem>
                                <Bootstrap.MenuItem eventKey="start">Start</Bootstrap.MenuItem>
                                <Bootstrap.MenuItem eventKey="stop">Stop</Bootstrap.MenuItem>
                            </Bootstrap.DropdownButton>
                        </td>
                    </tr>
                );
            }.bind(this));
            app_rows.push(rows);
        }

        var AppFormRedux = connect(function(state){
            return {auth: state.auth, apps: state.apps};
        })(AppForm);

        return (
            <div>
                <AppFormRedux hosts = {this.state.hosts} getHostInfo = {this.getHostInfo} />
                <Bootstrap.PageHeader>Current apps <small>All specified apps</small></Bootstrap.PageHeader>
                <Bootstrap.Table striped bordered hover>
                    <thead>
                        <tr>
                        <td>Hostname</td>
                        <td>IP</td>
                        <td>Size</td>
                        <td>Status</td>
                        <td>Host</td>
                        <td>Actions</td>
                        </tr>
                    </thead>
                    <tbody>
                        {app_rows}
                    </tbody>
                </Bootstrap.Table>
            </div>
        );
    }
});

var AppForm = React.createClass({
    getInitialState: function () {
        return {status: 'none', progress: 0, hosts: [], states: [], hostname: "", role: "", defaults: {image: "", network: "", sec_group: "", size: ""}, options: {sizes: [], networks: [], images: [], sec_groups: []}, host_usage: {cpu: "", maxCpu: "", ram: "", maxRam: "", disk: "", maxDisk: "", instances: "", maxInstances: ""}};
    },

    componentDidMount: function () {
        var me = this;
        Network.get('/api/hosts', this.props.auth.token).done(function (data) {
            me.setState({hosts: data.hosts});
            var host = data.hosts[0].hostname;
            me.setState({hostname: host});
            if(data.hosts.length > 0){
                var first_host = data.hosts[0];
                me.setState({options: {sizes: first_host.sizes, networks: first_host.networks, images: first_host.images, sec_groups: first_host.sec_groups}});
                me.setState({defaults: first_host.defaults});
            }
            if(me.props.hosts.length > 0){
                var host_usage = me.props.hosts[0].host_usage;
                if(Object.keys(host_usage).length > 0){
                    me.setState({host_usage: {cpu: host_usage.used_cpus, maxCpu: host_usage.max_cpus, ram: host_usage.used_ram, maxRam: host_usage.max_ram, disk: host_usage.used_disk, maxDisk: host_usage.max_disk, instances: host_usage.used_instances, maxInstances: host_usage.max_instances}});
                }
            }
        });
        Network.get('/api/states', this.props.auth.token).done(function (data) {
            me.setState({states: data});
            if(me.props.apps.select){
                me.setState({role: me.props.apps.select});
            }else{
                me.setState({role: data[0].name});
            }
        });
    },

    onChange: function(e) {
        value = e.target.value;
        this.setState({hostname: value});
        var i;
        for(i=0; i < this.state.hosts.length; i++){
            var host = this.state.hosts[i];
            if(host.hostname === value){
                this.setState({options: {sizes: host.sizes, networks: host.networks, images: host.images, sec_groups: host.sec_groups}});
                this.setState({defaults: host.defaults});
                break;
            }
        }
        var host_usage = this.props.hosts[i].host_usage;
        if(Object.keys(host_usage).length > 0){
            this.setState({host_usage: {cpu: host_usage.used_cpus, maxCpu: host_usage.max_cpus, ram: host_usage.used_ram, maxRam: host_usage.max_ram, disk: host_usage.used_disk, maxDisk: host_usage.max_disk, instances: host_usage.used_instances, maxInstances: host_usage.max_instances}});
        }else{
            this.setState({host_usage: {cpu: "", maxCpu: "", ram: "", maxRam: "", disk: "", maxDisk: "", instances: "", maxInstances: ""}});
        }
    },

    onChangeRole: function(e) {
        this.setState({role: e.target.value});
    },

    render: function () {
        var statusColor, statusDisplay, statusMessage;

        if(this.state.status == 'launching'){
            statusColor = 'yellow';
            statusDisplay = 'block';
            statusMessage = 'Launching... ' + this.state.progress + '%';
        }else if(this.state.status == 'launched'){
            statusColor = 'green';
            statusDisplay = 'block';
            statusMessage = 'Launched successfully!';
        }else {
            statusDisplay = 'none';
        }

        var me = this;

        var host_rows = this.state.hosts.map(function(host, i) {
            return <option key = {i}>{host.hostname}</option>
        });

        var state_rows = this.state.states.map(function(state) {
            if(state.name == me.props.apps.select){
                return <option key = {state.name} selected>{state.name}</option>
            }else{
                return <option key = {state.name}>{state.name}</option>
            }
        });

        var img_rows = this.state.options.images.map(function(img) {
            if(img == me.state.defaults.image){
                return <option key = {img} selected>{img}</option>
            }
            return <option key = {img}>{img}</option>
        });

        var sizes_rows = this.state.options.sizes.map(function(size) {
            if(size == me.state.defaults.size){
                return <option key = {size} selected>{size}</option>
            }
            return <option key = {size}>{size}</option>
        });

        var network_rows = this.state.options.networks.map(function(network) {
            if(network.split("|")[1] == me.state.defaults.network){
                return <option key = {network} selected>{network}</option>
            }
            return <option key = {network}>{network}</option>
        });

        var sec_groups = this.state.options.sec_groups.map(function(sec) {
            if(sec.split("|")[1] == me.state.defaults.sec_group){
                return <option key = {sec} selected>{sec}</option>
            }
            return <option key = {sec}>{sec}</option>
        });

        var StatsRedux = connect(function(state){
            return {auth: state.auth};
        })(Stats);

        return (
            <div className="container">
                <Bootstrap.Col xs={12} sm={6} md={6} className="app-column">
                    <Bootstrap.PageHeader className="header">Launch new app</Bootstrap.PageHeader>
                    <Bootstrap.Form onSubmit={this.onSubmit} horizontal>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col sm={4}>
                                <Bootstrap.FormControl componentClass="select" ref='role' onChange={this.onChangeRole}>
                                    {state_rows}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={8}>
                                <Bootstrap.FormControl type="text" ref='name' placeholder='Instance name' />
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Host
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl componentClass="select" ref='hostname' onChange={this.onChange}>
                                    {host_rows}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Image
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl componentClass="select" ref='image'>
                                    {img_rows}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Flavors
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl componentClass="select" ref='flavor'>
                                    {sizes_rows}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Storage disk
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl type="text" ref='storage' />
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Networks
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl componentClass="select" ref='network'>
                                    {network_rows}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.FormGroup>
                            <Bootstrap.Col componentClass={Bootstrap.ControlLabel} sm={2}>
                                Security group
                            </Bootstrap.Col>
                            <Bootstrap.Col sm={10}>
                                <Bootstrap.FormControl componentClass="select" ref='sec_group'>
                                    {sec_groups}
                                </Bootstrap.FormControl>
                            </Bootstrap.Col>
                        </Bootstrap.FormGroup>
                        <Bootstrap.ButtonGroup>
                            <Bootstrap.Button type="submit" bsStyle='primary'>
                                Launch
                            </Bootstrap.Button>
                        </Bootstrap.ButtonGroup>
                        <div style={{width: '100%', padding: 10, borderRadius: 5, background: statusColor, display: statusDisplay}}>
                            {statusMessage}
                        </div>
                    </Bootstrap.Form>
                </Bootstrap.Col>
                <StatsRedux hostname = {this.state.hostname} stats = {this.state.stats} host_usage = {this.state.host_usage} />
            </div>
        );
    },
    onSubmit: function(e) {
        e.preventDefault();
        var me = this;
        this.setState({status: 'launching', progress: 0});
        interval = setInterval(function(){
            if(me.state.status == 'launching' && me.state.progress <= 80){
                var newProgress = me.state.progress + 10;
                me.setState({progress: newProgress})
            }else{
                clearInterval(interval);
            }
        }, 10000);
        var data = {
            instance_name: ReactDOM.findDOMNode(this.refs.name).value,
            hostname: ReactDOM.findDOMNode(this.refs.hostname).value,
            role: ReactDOM.findDOMNode(this.refs.role).value,
            size: ReactDOM.findDOMNode(this.refs.flavor).value,
            image: ReactDOM.findDOMNode(this.refs.image).value,
            storage: ReactDOM.findDOMNode(this.refs.storage).value,
            network: ReactDOM.findDOMNode(this.refs.network).value,
            sec_group: ReactDOM.findDOMNode(this.refs.sec_group).value
        };
        Network.post('/api/apps', this.props.auth.token, data).done(function(data) {
            setTimeout(function(){
                me.setState({status: 'launched'});
                me.props.getHostInfo();
            }, 2000);
        });
    }
});

var Stats = React.createClass({
    render: function () {
        return (
            <Bootstrap.Col xs={12} sm={6} md={6}>
                <Bootstrap.PageHeader className="header">{this.props.hostname}</Bootstrap.PageHeader>
                <label>CPU: </label>{this.props.host_usage.cpu} / {this.props.host_usage.maxCpu}<br/>
                <label>RAM: </label>{this.props.host_usage.ram} / {this.props.host_usage.maxRam}<br/>
                <label>DISK: </label>{this.props.host_usage.disk} / {this.props.host_usage.maxDisk}<br/>
                <label>INSTANCES: </label>{this.props.host_usage.instances} / {this.props.host_usage.maxInstances}<br/>
            </Bootstrap.Col>
        );

    }
});

Apps = connect(function(state){
    return {auth: state.auth, apps: state.apps};
})(Appp);

module.exports = Apps;
