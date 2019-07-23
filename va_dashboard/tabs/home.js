import React, { Component } from 'react';
import {Router, Link, IndexLink, hashHistory} from 'react-router';
var Bootstrap = require('react-bootstrap');
import {connect} from 'react-redux';
var moment = require('moment');
var Notification=require('./notification');
// import { findDOMNode } from 'react-dom';

var Network = require('../network');

var SEVERITIES = {warning: { color: 'rgb(249, 196, 98)', icon: 'fa fa-exclamation-circle'}};
['notice', 'info', 'debug'].forEach(t => SEVERITIES[t] = { color: 'rgb(150, 230, 118)', icon: 'fa fa-info-circle'});
['emerg', 'alert', 'crit', 'err'].forEach(t => SEVERITIES[t] = { color: 'rgb(242, 140, 140)', icon: 'fa fa-times-circle '});

const NavLink = (props) => {
    var isActive = window.location.hash.indexOf(props.to) !== -1;
    var className = isActive ? 'active' : '';
    if(isActive){
        var activeKey = -1;
        if('activeKey' in props){ //this.props.to.indexOf('panel') > -1
            activeKey = props.activeKey;
        }
        window.localStorage.setItem('activeKey', activeKey);
    }
    if('tabs' in props){
        return (
            <Link to={props.to} className={className} activeClassName='active' onClick={props.show_tabs.bind(null, props.tabs)}>
                {props.children}
            </Link>
        );
    }
    if('tab' in props){
        return (
            <Link to={props.to} className={className} activeClassName='active'>
                {props.children}
            </Link>
        );
    }

    return (
        <Link to={props.to} className={className} activeClassName='active' onClick={props.reset_tabs}>
            {props.children}
        </Link>
    );
}

class Home extends Component {
    constructor (props) {
        super(props);
        console.log('Props', props);
        var activeKey = window.localStorage.getItem('activeKey');
        if(activeKey){
            activeKey = parseInt(activeKey);
        }else{
            activeKey = -1;
        }
        this.state = {
            'data': [],
            'collapse': false,
            'activeKey': activeKey,
            'userType': props.auth.userType,
            'stats': {}
        };
        this.show_tabs = this.show_tabs.bind(this);
        this.reset_tabs = this.reset_tabs.bind(this);
        this.getPanels = this.getPanels.bind(this);
        this.navbar_click = this.navbar_click.bind(this);
        this.handleAlertDismiss = this.handleAlertDismiss.bind(this);
        this.collapse = this.collapse.bind(this);
        this.togglePanels = this.togglePanels.bind(this);
        this.showUpperPanels=this.showUpperPanels.bind(this);
        this.showNavLinks=this.showNavLinks.bind(this);
    }
    show_tabs(key){
        this.props.dispatch({type: 'SHOW_TABS', key: key});
    }
    reset_tabs(){
        this.props.menu.showTabs && this.props.dispatch({type: 'RESET_TABS'});
    }
    getPanels() {
        var me = this;
        Network.get('/api/panels', this.props.auth.token).done(function (data) {
            me.setState({data: data});
        }).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
    }
    getStats() {
        var me = this;
        Network.get('/api/panels/stats', this.props.auth.token).done(function (data) {
            me.setState({stats: data});
        }).fail(function (msg) {
            me.props.dispatch({type: 'SHOW_ALERT', msg: msg});
        });
    }
    componentDidMount() {
        if(!this.props.auth.token){
            hashHistory.push('/login');
        }else{
            this.getPanels();
            this.getStats();
        }
    }
    componentWillReceiveProps(props) {
        if(!props.auth.token) {
            hashHistory.push('/login');
        }
        var activeKey = window.localStorage.getItem('activeKey') || -1;
        if(this.state.activeKey != activeKey){
            this.setState({activeKey: parseInt(activeKey)});
        }
    }
    navbar_click(key, event) {
        if(key === 'logout')
            this.props.dispatch({type: 'LOGOUT'});
        else if(key === 'users'){
            this.reset_tabs();
            this.props.dispatch({type: 'SHOW_TABS', key: 'users'});
            hashHistory.push('/users_users');
        }
        else if(key === 'api'){
            hashHistory.push('/api');
        }
    }
    collapse() {
        this.setState({collapse: !this.state.collapse});
        var me = this;
        setTimeout(function(){
            me.props.dispatch({type: 'COLLAPSE'});
        }, 300);
    }
    handleAlertDismiss() {
        this.props.dispatch({type: 'HIDE_ALERT'});
    }

    togglePanels(id) {
        var x = document.getElementById(id);
        console.log(id);
        if (x.style.display === "none") {
            x.style.display = "block";
        } else {
            x.style.display = "none";
        }
    }

    showNavLinks(){
        if(this.state.userType == 'admin'){
                        var navLinks=[];
                        navLinks.push(<Bootstrap.MenuItem eventKey='users'>Users</Bootstrap.MenuItem>);
                        navLinks.push(<Bootstrap.MenuItem eventKey='api'>API</Bootstrap.MenuItem>);
                        navLinks.push(<li role="presentation"><a role="menuitem" href="https://github.com/VapourApps/va_master/tree/master/docs" target="_blank">Help</a></li>);
                        return navLinks;
        }
        else{
            return(<div></div>);
        }
    }

    showUpperPanels(){
        console.log('User type: ', this.state.userType);
        if(this.state.userType == 'admin'){
           return (<div>
                            <li>
                            <IndexLink to='' activeClassName='active' onClick={this.reset_tabs}>
                                <Bootstrap.Glyphicon glyph='home' /> Overview</IndexLink>
                            </li>
                            
                            <li>
                            <NavLink to='providers' reset_tabs={this.reset_tabs}>
                                <Bootstrap.Glyphicon glyph='hdd' /> Infrastructure <span className="badge">{this.state.stats.providers}</span></NavLink>
                            </li>
                            
                            <li>
                            <NavLink to='servers' reset_tabs={this.reset_tabs}>
                                <span><i className='fa fa-server' /> Servers <span className="badge">{this.state.stats.servers}</span></span>
                            </NavLink>
                            </li>
                            
                            <li>
                            <NavLink to='store' reset_tabs={this.reset_tabs}>
                                <Bootstrap.Glyphicon glyph='th' /> Apps <span className="badge">{this.state.stats.apps}</span></NavLink>
                            </li>

                            <li>
                            <NavLink to='services' reset_tabs={this.reset_tabs}>
                                <Bootstrap.Glyphicon glyph='cloud' /> Services <span className="badge">{this.state.stats.services}</span></NavLink>
                            </li>
                            

                            <li>
                            <NavLink to='integrations' tabs='integrations' show_tabs={this.show_tabs}>
                                <span><i className='fa fa-exchange' /> Integrations <span className="badge">{this.state.stats.integrations}</span></span>
                            </NavLink>
                            </li>

                            <li>
                            <NavLink to='vpn_status' tabs='vpn' show_tabs={this.show_tabs}>
                                <span><i className='fa fa-lock' /> VPN <span className="badge">{this.state.stats.vpn}</span></span>
                            </NavLink>
                            </li>

                            <li>
                            <NavLink to='log' reset_tabs={this.reset_tabs}>
                                <span><i className='fa fa-bar-chart' /> Log</span>
                            </NavLink>
                            </li>

                            <li>
                            <NavLink to='billing' reset_tabs={this.reset_tabs}>
                                <span><i className='fa fa-credit-card' /> Billing</span>
                            </NavLink>
                            </li>

                            <li role="separator" className="divider-vertical"></li>
                            <li className="panels-title">Admin panels</li>
                    </div>);
        }

        else{
            return(
                <div>
                    <li role="separator" className="divider-vertical"></li>
                    <li className="panels-title">User panels</li>
                </div>
            );
        }
    }

    render() {
        var me = this;
        var panels = this.state.data.filter(function(panel) {
            if(panel.servers.length > 0){
                return true;
            }
            return false;
        }).map(function(panel, i) {
            var header = (
                <a className="noselect" onClick={() => me.togglePanels("collapse"+i)} style={{cursor: 'pointer'}}> <i className={'fa ' + panel.icon} /> {panel.name} <i className='fa fa-angle-down pull-right' /></a>
            )
            var servers = panel.servers.map((server, j) => {
                var server_header = (
                    <a className="noselect" onClick={() => me.togglePanels("subpanel_collapse"+server + i)} style={{cursor: 'pointer'}}> {server} <i className='fa fa-angle-down pull-right' /></a>
                )
                var subpanels = panel.panels.map((subpanel) => {
                    return (
                        <li key={subpanel.key}><NavLink to={'panel/' + subpanel.key + '/' + server} activeKey={i} reset_tabs={me.reset_tabs}>
                            <span>{subpanel.name}</span>
                        </NavLink></li>
                    );
                });
                return (
                    <div key={server}>
                        {server_header}
                        <div id={"subpanel_collapse"+server +i} style={{display:'none'}}>
                        <ul className='left-menu'>
                            {subpanels}
                        </ul>
                        </div>
                    </div>
                );
            });
            return (
                <div>
                    {header}
                    <div id={"collapse" + i} style={{display:'none'}}>
                        {servers}
                    </div>
                </div>
            );
        });
        var key = this.props.menu.showTabs || window.location.hash.split('_')[0].slice(2);
        var menu_tabs = key in this.props.menu.tabs ? this.props.menu.tabs[key] : [];
        var tabs = menu_tabs.map(function(tab){
            return <li key={tab.title}><NavLink to={tab.link} tab>{tab.title}</NavLink></li>
        });
        /*var navLinks = [{to: 'providers', glyph: 'hdd'}, {to: 'servers', klasa: 'server'},
            {to: 'store', glyph: 'th'}, {to: 'services', glyph: 'cloud'},
            {to: 'servers', klasa: 'server'}, {to: 'servers', klasa: 'server'}
        ];*/


        return (
            <div id="app-content">
                <Bootstrap.Navbar bsStyle='inverse'>
                    <Bootstrap.Navbar.Header>
                        <Bootstrap.Glyphicon glyph='menu-hamburger' onClick={this.collapse} />
                        <img src='/static/logo.png' className='top-logo'/>
                        <Bootstrap.Navbar.Toggle />
                    </Bootstrap.Navbar.Header>
                    <Bootstrap.Navbar.Collapse>
                        {tabs.length > 0 && <Bootstrap.Nav>
                            {tabs}
                        </Bootstrap.Nav>}
                        <Bootstrap.Nav pullRight>
                            <Bootstrap.NavDropdown title={this.props.auth.username} onSelect={this.navbar_click} id="nav-dropdown" pullRight>
                                    {this.showNavLinks()}
                                    <Bootstrap.MenuItem eventKey='logout'>Logout</Bootstrap.MenuItem>
                            </Bootstrap.NavDropdown>
                        </Bootstrap.Nav>
                        <Notification />
                    </Bootstrap.Navbar.Collapse>
                </Bootstrap.Navbar>
                <div className='main-content'>
                    <div className='sidebar' style={this.state.collapse?{display: 'none'}:{display: 'flex'}}>
                        <ul className='left-menu'>
                                {this.showUpperPanels()}
                            <li>
                                    {panels}
                            </li>
                        </ul>
                    </div>
                    <div className="page-content">
                        {this.props.children}
                    </div>
                    {this.props.alert.show && React.createElement(Bootstrap.Alert, {bsStyle: this.props.alert.className, onDismiss: this.handleAlertDismiss, className: "messages"}, this.props.alert.msg) }
                </div>
                <div className="footer">
                    Powered by <a href="//vapour-apps.com" target="_blank">VapourApps</a> | <a href="mailto:support@vapour-apps.com">support@vapour-apps.com</a>
                </div>
            </div>
        );
    }
}

/*class Notification extends Component {
  constructor (props) {
    super(props);
    this.state = {
      show: false,
      newNotification: false
    }
    this.handleToggle = this.handleToggle.bind(this);
    this.readAll = this.readAll.bind(this);
  }

  handleToggle() {
    this.setState({ show: !this.state.show, newNotification: false });
  }

  componentWillUpdate(newProps) {
    if(newProps.newNotifications != this.props.newNotifications && newProps.newNotifications.length)
      this.setState({newNotification: true})
  }

  renderNotifications(n, className) {
    return n.map((n, i) => {
      const severity = SEVERITIES[n.severity];
      return (
        <div key={i} style={styles.row} className={className}>
          <i className={severity.icon} style={{fontSize: '30px', color: severity.color}} />
          <div style={styles.body}>
            <div style={styles.text}>{n.message}</div>
            <div style={styles.flexContainer}>
              <div style={styles.subText}>{moment(n.timestamp).fromNow()}</div>
              <div style={styles.subText}>{n.host}</div>
            </div>
          </div>
        </div>
      );
    });
  }

  readAll() {
    this.props.dispatch({ type: 'READ_ALL_NOTIFICATIONS' });
  }

  render() {
    let classname = 'fa fa-bell fa-lg';
    if(this.state.newNotification) {
      classname += ' notification'
    }
    console.log("notifications", this.props.notifications);
    console.log("newNotifications", this.props.newNotifications);
    return (
      <Bootstrap.Nav pullRight>
        <span style={{position: 'relative'}}>
          <i
            className={classname}
            style={{color: '#fff', cursor: 'pointer'}}
            onClick={this.handleToggle}
          />
        </span>
        {this.state.show && [
            <div style={styles.overlay} onClick={this.handleToggle}></div>,
            <div style={styles.popup} id="notification-popup">
              <div style={styles.scroller}>
                {this.renderNotifications(this.props.newNotifications, 'new-notification')}
                {this.renderNotifications(this.props.notifications, '')}
              </div>
              <div style={styles.popupFooter}>
                <span className='clickable' onClick={this.readAll}>Read all notifications</span>
              </div>
            </div>]}
      </Bootstrap.Nav>
    )
  }
}
*/

/*const NotificationRedux = connect(function(state) {
    return {auth: state.auth, ...state.notifications}
})(Notification);
*/

const styles = {
  popup: {
    position: 'absolute',
    top: 55, //100%
    right: 65, //-15,
    backgroundColor: '#fff',
    width: 358,
    zIndex: 1000,
    border: '1px solid rgba(235,235,235,0.4)',
  },
  scroller: {
    overflowY: 'auto',
    maxHeight: 400,
  },
  overlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: '100%',
    height: '100%',
    zIndex: 500
  },
  row: {
    borderBottom: '1px solid rgba(77,82,89,0.07)',
    padding: '10px',
    display: 'flex',
    alignItems: 'center'
  },
  body: {
    flexGrow: 1,
    paddingLeft: 8,
    minWidth: 0
  },
  text: {
    overflow: 'hidden',
    whiteSpace: 'nowrap',
    textOverflow: 'ellipsis',
    lineHeight: '26px',
    fontSize: 13,
    height: '26px'
  },
  subText: {
    fontSize: 12,
    color: '#8b95a5'
  },
  flexContainer: {
    display: 'flex',
    justifyContent: 'space-between',
    lineHeight: '26px'
  },
  icon: {
    fontSize: '20px'
  },
  popupFooter: {
    backgroundColor: '#f9fafb',
    padding: '8px 10px',
    color: '#8b95a5',
    height: 46,
    display: 'flex',
    alignItems: 'center'
  }
}

module.exports = connect(function(state) {
    return {auth: state.auth, alert: state.alert, menu: state.menu}
})(Home);
