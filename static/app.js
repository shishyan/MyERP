/**
 * OpenNow — Zen AI-Native Enterprise Service Platform & Incident Command
 * Lead Frontend Architecture & Interactions
 * Pure Vanilla ES6+ (Zero Build Dependencies, Instant Execution)
 */

(function () {
  'use strict';

  // =========================================================================
  // STATE MANAGEMENT & SAMPLE DATASET
  // =========================================================================

  const DEFAULT_TAXONOMY = {
    'Database & Storage': {
      'PostgreSQL Aurora': [
        'Connection Pooler Exhaustion',
        'Deadlock / Lock Contention',
        'Replication Lag Breach',
        'Disk IOPS Throttling',
        'Slow Query Plan Regression'
      ],
      'Redis Cache': [
        'Memory Pressure / OOM Eviction',
        'Cluster Sentinel Failover',
        'Key TTL Expiration Anomaly',
        'Persistence AOF/RDB Stall'
      ],
      'Kafka Event Bus': [
        'Consumer Group Lag Breach',
        'Broker Disk Space Full',
        'Under-Replicated Partitions',
        'Metadata Partition Desync'
      ]
    },
    'Software & Applications': {
      'Payment Gateway': [
        'Webhook 504 Timeout',
        '3DS Verification Drop',
        'Stripe API Rate Limiting',
        'Settlement Reconciliation Mismatch'
      ],
      'Auth & Identity (Auth0)': [
        'JWKS Key Retrieval Latency',
        'SAML / SSO Assertion Failure',
        'Token Signature Validation Error',
        'MFA Provider Intermittent Drops'
      ],
      'Order & Checkout Service': [
        'Cart Checkout 500 Spike',
        'Inventory Lock Starvation',
        'Discount Engine Calculation Error'
      ]
    },
    'Cloud & Infrastructure': {
      'Kubernetes Cluster (EKS)': [
        'Worker Node OOM / NotReady',
        'Pod CrashLoopBackOff Surge',
        'CoreDNS Resolution Throttling',
        'EBS Volume Detach Timeout'
      ],
      'API Gateway (Kong)': [
        'TLS Certificate Auto-Renewal Failure',
        'Envoy Worker Thread Core Dump',
        'Rate Limiting Plugin Failure',
        'Upstream Health Check Flapping'
      ],
      'Edge & CDN (Cloudflare)': [
        'HTTP/3 QUIC UDP Fallback',
        'Anycast DNS Routing Degraded',
        'WAF Rule False Positive Surge',
        'Origin Shield Cache Stampede'
      ]
    },
    'Security & Compliance': {
      'Access Control & IAM': [
        'Privileged Role Escalation Alert',
        'Service Account Key Rotation Failure',
        'KMS Decryption Quota Reached'
      ],
      'Vulnerability & Patching': [
        'Zero-Day Vulnerability Advisory',
        'SSL/TLS Weak Cipher Detected',
        'Container Image CVE High Severity'
      ]
    }
  };

  const DEFAULT_PRIORITY_MATRIX = {
    'Enterprise': { 'Critical': 'P1', 'High': 'P1', 'Medium': 'P2', 'Low': 'P3' },
    'Department': { 'Critical': 'P1', 'High': 'P2', 'Medium': 'P3', 'Low': 'P4' },
    'Single User': { 'Critical': 'P2', 'High': 'P3', 'Medium': 'P4', 'Low': 'P4' }
  };

  const DEFAULT_SLA_POLICIES = {
    'P1': { name: 'P1 Critical SLA', resolveHours: 1, responseMins: 15, schedule: '24x7', escalationTimerMins: 30, pauseOnHold: true },
    'P2': { name: 'P2 High SLA', resolveHours: 4, responseMins: 30, schedule: '24x7', escalationTimerMins: 120, pauseOnHold: true },
    'P3': { name: 'P3 Medium SLA', resolveHours: 12, responseMins: 60, schedule: 'business', escalationTimerMins: 360, pauseOnHold: true },
    'P4': { name: 'P4 Low SLA', resolveHours: 48, responseMins: 240, schedule: 'business', escalationTimerMins: 1440, pauseOnHold: true }
  };

  const DEFAULT_SLA_SCHEDULES = {
    scheduleMode: '24x7',
    timezone: 'UTC',
    pauseOnHold: true,
    pausePendingCustomer: true,
    pausePendingVendor: true,
    pausePendingChange: true,
    p1ThresholdMins: 30,
    p2ThresholdMins: 60
  };

  const DEFAULT_RESOLUTION_CODES = [
    'Software Patch / Deploy',
    'Workaround Applied',
    'Configuration Tuning',
    'Hardware Fix / Replacement',
    'User Training / Doc Update',
    'Third-Party Vendor Resolved'
  ];

  const DEFAULT_ROOT_CAUSES = [
    'Memory Leak / GC Pause',
    'Database Deadlock / Pool Exhaustion',
    'Network / DNS Latency Flap',
    'Human Error / Config Misconfiguration',
    'Upstream Cloud Provider Outage',
    'Third-Party API Rate Limit'
  ];

  const DEFAULT_TECHNICIANS = [
    { id: 'TECH-1', name: 'Alex Rivera', role: 'Lead SRE Architect', group: 'SRE-Core', rate: 150, status: 'Active' },
    { id: 'TECH-2', name: 'David Chen', role: 'Senior Database Administrator', group: 'Database-Ops', rate: 165, status: 'Active' },
    { id: 'TECH-3', name: 'Sarah Lin', role: 'Cloud Platform Engineer', group: 'Cloud-Infra', rate: 145, status: 'Active' },
    { id: 'TECH-4', name: 'Marcus Vance', role: 'Principal Security Engineer', group: 'Security-SecOps', rate: 180, status: 'Active' },
    { id: 'TECH-5', name: 'Elena Rostova', role: 'SRE Reliability Engineer', group: 'Payment-Platform', rate: 140, status: 'Active' }
  ];

  const DEFAULT_BUSINESS_RULES = [
    { id: 'BR-1', name: 'Auto-route Database Incidents', enabled: true, conditionField: 'category', conditionOperator: 'equals', conditionValue: 'Database & Storage', targetTeam: 'Database-Ops', targetPriority: 'P1' },
    { id: 'BR-2', name: 'Auto-escalate Payment Gateway Outages', enabled: true, conditionField: 'ci', conditionOperator: 'equals', conditionValue: 'CI-PAY-003', targetTeam: 'Payment-Platform', targetPriority: 'P1' },
    { id: 'BR-3', name: 'Security & Compliance Lockdown', enabled: true, conditionField: 'category', conditionOperator: 'equals', conditionValue: 'Security & Compliance', targetTeam: 'Security-SecOps', targetPriority: 'P1' },
    { id: 'BR-4', name: 'Cloud Infrastructure Direct Routing', enabled: true, conditionField: 'category', conditionOperator: 'equals', conditionValue: 'Cloud & Infrastructure', targetTeam: 'Cloud-Infra', targetPriority: 'P2' }
  ];


  // =========================================================================
  // ITSM EXPANSIONS: PROBLEM, CHANGE, KB, OMNICHANNEL DATASETS
  // =========================================================================

  const DEFAULT_PROBLEMS = [
    {
      id: 'PRB-101',
      title: 'Recurring PostgreSQL Deadlock & Connection Pool Saturation',
      ci: 'CI-DB-001',
      ciName: 'PostgreSQL Primary (us-east-1)',
      status: 'Known Error',
      isKedb: true,
      category: 'Database & Storage',
      rootCause: 'Batch analytics cron executed unindexed full-table join during peak customer traffic hours.',
      workaround: 'Execute pg_terminate_backend on idle connections holding RowExclusiveLock; scale PgBouncer to 6 replicas.',
      linkedIncidents: ['INC-9041', 'INC-9043'],
      whys: [
        { q: 'Why did database response time breach SLA?', a: 'Connections exceeded the max pool limit of 500 active threads.' },
        { q: 'Why did active connections reach pool exhaustion?', a: 'Multiple transaction threads were waiting on RowExclusiveLock.' },
        { q: 'Why were locks held open for >120 seconds?', a: 'A reporting query was executing an unindexed multi-table Cartesian product.' },
        { q: 'Why was the unindexed reporting query running during peak traffic?', a: 'The cron job scheduler was configured in UTC without peak-hour suppression.' },
        { q: 'Root Cause: Why did CI/CD allow this query without an index?', a: 'Deployment linting lacked an automated index-validation gate for raw SQL migrations.' }
      ]
    },
    {
      id: 'PRB-102',
      title: 'Redis Cluster Memory Eviction & Session Desync Under Load',
      ci: 'CI-CACHE-002',
      ciName: 'Redis Session & Cache',
      status: 'Known Error',
      isKedb: true,
      category: 'Database & Storage',
      rootCause: 'Auth0 JWT refresh tokens stored with missing TTL expiration metadata.',
      workaround: 'Run safe keyspace SCAN script and configure volatile-lru eviction policy across replica nodes.',
      linkedIncidents: ['INC-9044'],
      whys: [
        { q: 'Why were active user sessions getting logged out?', a: 'Redis was evicting keys due to reaching maxmemory threshold.' },
        { q: 'Why was Redis memory consumption above 88%?', a: 'Expired auth tokens were not being garbage collected.' },
        { q: 'Why did tokens not expire automatically?', a: 'Auth service omitted the EXPIRE flag during Redis SET command.' },
        { q: 'Why was the omission not caught in staging?', a: 'Staging environment had synthetic low session cardinality.' },
        { q: 'Root Cause: Why was session token code modified without contract testing?', a: 'Legacy session handler refactor bypassed contract unit tests for cache keys.' }
      ]
    },
    {
      id: 'PRB-103',
      title: 'Kong Ingress TLS Certificate Auto-Renewal Verification Timeout',
      ci: 'CI-INGRESS-005',
      ciName: 'Kong API Gateway',
      status: 'Under Investigation',
      isKedb: false,
      category: 'Cloud & Infrastructure',
      rootCause: 'AWS Route53 DNS-01 challenge timed out due to IAM permission role boundary.',
      workaround: 'Manually apply IAM trust policy and trigger cert-manager verification via CLI.',
      linkedIncidents: ['INC-9045'],
      whys: [
        { q: 'Why was TLS certificate renewal failing?', a: 'Let\'s Encrypt DNS-01 challenge timed out after 3 retries.' },
        { q: 'Why did the DNS challenge time out?', a: 'Cert-manager could not write TXT record to AWS Route53.' },
        { q: 'Why was TXT record creation rejected?', a: 'The IAM service account lacked route53:ChangeResourceRecordSets permissions.' },
        { q: 'Why did the IAM role lack permissions?', a: 'A recent IAM boundary policy update tightened cross-account roles.' },
        { q: 'Root Cause: Why was the service account role boundary changed?', a: 'SecOps policy push applied broad restrictions without service account exemption list.' }
      ]
    }
  ];

  const DEFAULT_CHANGES = [
    {
      id: 'CHG-401',
      title: 'Aurora PostgreSQL 15.4 Minor Engine & Security Patch Upgrade',
      ci: 'CI-DB-001',
      ciName: 'PostgreSQL Primary (us-east-1)',
      type: 'Normal',
      riskScore: 28,
      riskLevel: 'Low',
      cabStatus: 'Pending CAB Approval',
      scheduled: 'Sunday 02:00 - 03:00 UTC',
      lead: 'David Chen (DBA)',
      rollbackPlan: 'Automated point-in-time snapshot restore (RTO: 8 min, RPO: 0 sec)'
    },
    {
      id: 'CHG-402',
      title: 'EKS Core Cluster Worker Node Autoscaling Capacity Boost',
      ci: 'CI-K8S-006',
      ciName: 'EKS Core Cluster (us-east-1)',
      type: 'Standard',
      riskScore: 14,
      riskLevel: 'Low',
      cabStatus: 'Approved by CAB',
      scheduled: 'Continuous / Zero-Downtime',
      lead: 'Alex Rivera (SRE)',
      rollbackPlan: 'Karpenter autoscaler min/max node group rollback via git commit'
    },
    {
      id: 'CHG-403',
      title: 'Kong Ingress Envoy Proxy Hot-Patch for Rate Limiting Plugin',
      ci: 'CI-INGRESS-005',
      ciName: 'Kong API Gateway',
      type: 'Emergency',
      riskScore: 68,
      riskLevel: 'Medium',
      cabStatus: 'Pending CAB Approval',
      scheduled: 'Today 18:30 UTC',
      lead: 'Sarah Lin (Cloud)',
      rollbackPlan: 'Container image rollback to digest SHA:9b4f2c with Envoy restart'
    },
    {
      id: 'CHG-404',
      title: 'Cloudflare WAF Custom Bot Management Rule Set Deployment',
      ci: 'CI-CDN-008',
      ciName: 'Cloudflare Global Edge',
      type: 'Normal',
      riskScore: 38,
      riskLevel: 'Low',
      cabStatus: 'Approved by CAB',
      scheduled: 'Saturday 01:00 UTC',
      lead: 'Marcus Vance (SecOps)',
      rollbackPlan: 'Instant bypass rule toggle via Cloudflare Terraform provider'
    }
  ];

  const DEFAULT_KB_ARTICLES = [
    {
      id: 'KB-201',
      title: 'Remediating Aurora PostgreSQL Lock Contention & Connection Spikes',
      category: 'Databases',
      author: 'David Chen (DBA)',
      views: 418,
      helpfulUp: 142,
      helpfulDown: 3,
      verified: true,
      summary: 'Diagnostic SQL queries using pg_stat_activity and lock termination procedures to restore healthy connection pools.',
      content: `
        <h4>Summary of Problem</h4>
        <p>When batch reporting or unindexed transactions execute during peak checkout hours, PostgreSQL connections enter <code>idle in transaction</code> state while holding <code>RowExclusiveLock</code>. This exhausts the PgBouncer pool and returns 504 Gateway Timeouts to upstream API clients.</p>
        
        <h4 class="mt-2">Diagnostic Command</h4>
        <div class="ai-command-snippet">
SELECT pid, now() - query_start AS duration, query, state 
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY duration DESC LIMIT 10;
        </div>

        <h4 class="mt-2">Remediation Steps</h4>
        <ol style="padding-left:18px; margin-top:6px; line-height:1.6;">
          <li>Identify blocking backend PID from the query above.</li>
          <li>Execute graceful backend termination: <code>SELECT pg_cancel_backend(pid);</code></li>
          <li>If unresponsive after 15 seconds, force terminate: <code>SELECT pg_terminate_backend(pid);</code></li>
          <li>Temporarily scale PgBouncer replicas: <code>kubectl scale deployment/pgbouncer --replicas=6 -n database</code></li>
        </ol>
      `
    },
    {
      id: 'KB-202',
      title: 'EKS Worker Node OOM & CrashLoopBackOff Recovery Playbook',
      category: 'Cloud & Infra',
      author: 'Alex Rivera (SRE)',
      views: 632,
      helpfulUp: 215,
      helpfulDown: 5,
      verified: true,
      summary: 'SOP for diagnosing memory-leaking container pods, draining cordoned nodes safely, and adjusting resource limits.',
      content: `
        <h4>Symptoms & Alerts</h4>
        <p>Prometheus alert <code>KubeNodeMemoryPressure</code> fired. Worker nodes reporting <code>NotReady</code> status due to container memory exceedance.</p>
        
        <h4 class="mt-2">Drain & Quarantine Node</h4>
        <div class="ai-command-snippet">
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
        </div>

        <h4 class="mt-2">Verification</h4>
        <p>Check node conditions: <code>kubectl describe node &lt;node-name&gt; | grep -A 5 Conditions</code></p>
      `
    },
    {
      id: 'KB-203',
      title: 'Kong Ingress TLS Wildcard Certificate Rotation via Cert-Manager',
      category: 'Security',
      author: 'Sarah Lin (Cloud)',
      views: 320,
      helpfulUp: 98,
      helpfulDown: 2,
      verified: true,
      summary: 'Standard operating procedure for ACME DNS-01 challenge troubleshooting and Route53 permission verification.',
      content: `
        <h4>ACME DNS-01 Verification</h4>
        <p>Cert-manager requires AWS Route53 access to create challenge TXT records. If Route53 rate limits occur, manual intervention is required.</p>
        <div class="ai-command-snippet">
kubectl describe certificaterequest -n kong-ingress
cmctl renew wildcard-opennow-tls -n kong-ingress
        </div>
      `
    },
    {
      id: 'KB-204',
      title: 'Redis Cache Memory Eviction: Keyspace Optimization & TTL Audit',
      category: 'Databases',
      author: 'David Chen (DBA)',
      views: 285,
      helpfulUp: 87,
      helpfulDown: 1,
      verified: true,
      summary: 'Procedure for auditing unexpired session tokens, scanning keyspace memory, and configuring volatile-lru eviction.',
      content: `
        <h4>Keyspace Verification</h4>
        <p>Audit keys without TTL: <code>redis-cli --bigkeys</code></p>
        <p>Verify active eviction policy: <code>CONFIG GET maxmemory-policy</code></p>
      `
    }
  ];

  const DEFAULT_EMAIL_CHANNELS = [
    { id: 'EM-1', email: 'support@opennow.io', name: 'Primary Customer Support Mailbox', imap: 'imap.opennow.io:993', ssl: true, team: 'SRE-Core', priority: 'P2', active: true },
    { id: 'EM-2', email: 'critical-ops@opennow.io', name: 'Executive & Automated Alarm Intake', imap: 'imap-urgent.opennow.io:993', ssl: true, team: 'SRE-Core', priority: 'P1', active: true }
  ];

  const DEFAULT_PHONE_CTI = {
    provider: 'WebRTC / Amazon Connect',
    screenPopEnabled: true,
    ciLookupEnabled: true,
    whisperAiEnabled: true,
    autoWorklogEnabled: true,
    callerPhone: '+1 (415) 555-0199',
    callerName: 'Sarah Lin',
    callerTitle: 'VP of Infrastructure & Cloud Ops',
    callerCi: 'CI-K8S-006'
  };

  let CLASSIFICATION_DATA = DEFAULT_TAXONOMY;

  function calculatePriority(impact, urgency) {
    if (state && state.priorityMatrix && state.priorityMatrix[impact] && state.priorityMatrix[impact][urgency]) {
      return state.priorityMatrix[impact][urgency];
    }
    if (impact === 'Enterprise') {
      if (urgency === 'Critical' || urgency === 'High') return 'P1';
      if (urgency === 'Medium') return 'P2';
      return 'P3';
    } else if (impact === 'Department') {
      if (urgency === 'Critical') return 'P1';
      if (urgency === 'High') return 'P2';
      if (urgency === 'Medium') return 'P3';
      return 'P4';
    } else { // Single User
      if (urgency === 'Critical') return 'P2';
      if (urgency === 'High') return 'P3';
      return 'P4';
    }
  }

  function getPriorityLabel(priority) {
    switch (priority) {
      case 'P1': return 'P1 Critical (Full Outage)';
      case 'P2': return 'P2 High (Major Degradation)';
      case 'P3': return 'P3 Moderate (Partial Defect)';
      case 'P4': return 'P4 Low (Minor / Advisory)';
      default: return priority;
    }
  }

  function formatDurationShort(totalSeconds) {
    if (!totalSeconds || totalSeconds <= 0) return '0s';
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    if (hrs > 0) return `${hrs}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  }


  const DEFAULT_SERVICE_REQUESTS = [
    {
      id: 'REQ-101',
      title: 'MacBook Pro 16" M3 Max (64GB RAM, 1TB SSD) Developer Workstation',
      catalogItem: 'Developer Workstation (MacBook Pro M3 Max)',
      category: 'Hardware & Devices',
      requester: 'maya.patel@opennow.io',
      requesterName: 'Maya Patel',
      department: 'Site Reliability Engineering',
      priority: 'P2',
      status: 'IN_PROGRESS',
      stage: 'In Procurement / Asset Tagging',
      approver: 'Sarah Lin (Engineering Director)',
      approvalStatus: 'Approved by Director',
      assignedTeam: 'IT-Asset-Management',
      assignedTo: 'Carlos Mendes',
      createdAt: '2 hours ago',
      slaDue: 'Tomorrow 18:00 UTC (22h left)',
      slaHoursRemaining: 22,
      cost: 3899.00,
      justification: 'New hire onboarding for Principal Distributed Systems Architect.',
      specs: { 'Chip': 'Apple M3 Max (16-core CPU)', 'Unified Memory': '64GB', 'Storage': '1TB NVMe', 'Peripherals': 'Dual Studio Displays' }
    },
    {
      id: 'REQ-102',
      title: 'Production AWS VPC Cross-Account Peering & IAM ReadRole',
      catalogItem: 'Cloud Infrastructure / AWS IAM Role',
      category: 'Cloud & Access',
      requester: 'elena.rostova@opennow.io',
      requesterName: 'Elena Rostova',
      department: 'Payment Engineering',
      priority: 'P1',
      status: 'NEW',
      stage: 'Pending SecOps Approval',
      approver: 'Marcus Vance (Principal SecOps)',
      approvalStatus: 'Pending Security Review',
      assignedTeam: 'Cloud-Infra',
      assignedTo: 'Sarah Lin',
      createdAt: '45 mins ago',
      slaDue: 'Today 21:00 UTC (4h left)',
      slaHoursRemaining: 4,
      cost: 0.00,
      justification: 'Payment reconciliation microservice migration requires access to analytics Aurora RDS read replica.',
      specs: { 'Account': 'AWS Production (Acct: 492019481)', 'Role Requested': 'arn:aws:iam::role/FinTechPeeringRole', 'MFA Enforced': 'Yes' }
    },
    {
      id: 'REQ-103',
      title: 'JetBrains All Products Pack Enterprise Subscription Renewal',
      catalogItem: 'Software Development IDE License',
      category: 'Software & SaaS',
      requester: 'david.chen@opennow.io',
      requesterName: 'David Chen',
      department: 'Database Operations',
      priority: 'P3',
      status: 'RESOLVED',
      stage: 'Fulfilled & Delivered',
      approver: 'Alex Rivera (Lead Architect)',
      approvalStatus: 'Approved',
      assignedTeam: 'IT-Software-Procurement',
      assignedTo: 'Carlos Mendes',
      createdAt: '1 day ago',
      slaDue: '✓ Delivered within SLA',
      slaHoursRemaining: 0,
      cost: 499.00,
      justification: 'Annual license renewal for DataGrip and IntelliJ Ultimate for database performance tuning.',
      specs: { 'Vendor': 'JetBrains', 'Seats': '1 Enterprise Seat', 'License Key': 'JB-ENT-9942-8812-FL' }
    },
    {
      id: 'REQ-104',
      title: 'High-Throughput Kafka Cluster Dedicated Topic Provisioning',
      catalogItem: 'Event Bus / Kafka Dedicated Topic',
      category: 'Cloud & Access',
      requester: 'kevin.zhao@opennow.io',
      requesterName: 'Kevin Zhao',
      department: 'Event Analytics',
      priority: 'P2',
      status: 'IN_PROGRESS',
      stage: 'Terraform Automation Running',
      approver: 'Alex Rivera (Lead Architect)',
      approvalStatus: 'Approved',
      assignedTeam: 'SRE-Core',
      assignedTo: 'Alex Rivera',
      createdAt: '3 hours ago',
      slaDue: 'Today 23:00 UTC (6h left)',
      slaHoursRemaining: 6,
      cost: 150.00,
      justification: 'Ingesting 120,000 real-time checkout telemetry events per second requires 12 partitions with 7-day retention.',
      specs: { 'Topic Name': 'orders.payment.telemetry.v2', 'Partitions': '12', 'Replication Factor': '3', 'Cleanup Policy': 'delete' }
    }
  ];

  const state = {
    currentView: 'incident-command',
    viewMode: 'table', // default table view
    zenMode: false,
    sidebarCollapsed: false,
    searchQuery: '',
    priorityFilter: 'ALL',
    teamFilter: 'ALL',
    selectedTicket: null,
    selectedNode: null,
    isBlastSimulating: false,
    currentPlatform: 'servicenow',
    activeSchemaTab: 'tasks',
    activeDrawerTab: 'overview',

    // Company DNA & Industry Archetype
    industry: 'fintech',
    companyDna: {
      industry_id: 'fintech',
      industry_name: 'FinTech, Banking & Capital Markets',
      sub_industry: 'Payment Processing & Acquiring',
      offering: 'Global Payment Gateway & Card Settlement',
      tech_stack: 'Kafka, PostgreSQL Aurora, Redis, HSM, Kubernetes, Go',
      compliance_framework: 'PCI-DSS Level 1 / SOC2 Type II',
      downtime_cost_per_minute: 18500
    },
    industryBlueprints: [],

    // ERP Setup & Master Data
    taxonomy: JSON.parse(JSON.stringify(DEFAULT_TAXONOMY)),
    priorityMatrix: JSON.parse(JSON.stringify(DEFAULT_PRIORITY_MATRIX)),
    slaPolicies: JSON.parse(JSON.stringify(DEFAULT_SLA_POLICIES)),
    slaSchedules: JSON.parse(JSON.stringify(DEFAULT_SLA_SCHEDULES)),
    resolutionCodes: [...DEFAULT_RESOLUTION_CODES],
    rootCauses: [...DEFAULT_ROOT_CAUSES],
    technicians: JSON.parse(JSON.stringify(DEFAULT_TECHNICIANS)),
    businessRules: JSON.parse(JSON.stringify(DEFAULT_BUSINESS_RULES)),
    activeSetupModule: 'dna',
    selectedTreeCat: 'Database & Storage',
    selectedTreeSubcat: 'PostgreSQL Aurora',

    // ITSM Collections
    problems: JSON.parse(JSON.stringify(DEFAULT_PROBLEMS)),
    filterKedbOnly: false,
    changes: JSON.parse(JSON.stringify(DEFAULT_CHANGES)),
    changeTypeFilter: 'ALL',
    kbArticles: JSON.parse(JSON.stringify(DEFAULT_KB_ARTICLES)),
    kbCatFilter: 'ALL',
    emailChannels: JSON.parse(JSON.stringify(DEFAULT_EMAIL_CHANNELS)),
    phoneCti: JSON.parse(JSON.stringify(DEFAULT_PHONE_CTI)),
    ctiSeconds: 48,

    stats: {
      activeIncidents: 12,
      p1Count: 2,
      cmdbHealth: 94.8,
      slaRate: 98.2
    },

    // CMDB Topology Configuration Items
    cmdbNodes: [
      {
        id: 'CI-CDN-008',
        name: 'Cloudflare Global Edge',
        tier: 'Edge',
        type: 'Edge & CDN',
        health: 'healthy',
        team: '@sre-edge',
        provider: 'Cloudflare Anycast',
        x: 80,
        y: 160,
        cpu: 18,
        mem: 32,
        latency: 14,
        errors: 0.01,
        uptime: '99.99%',
        upstream: [],
        downstream: ['CI-INGRESS-005'],
        activeIncidents: ['INC-9049']
      },
      {
        id: 'CI-INGRESS-005',
        name: 'Kong API Gateway',
        tier: 'Gateway',
        type: 'API Gateway Ingress',
        health: 'degraded',
        team: '@cloud-infra',
        provider: 'AWS us-east-1 (Envoy / Kong)',
        x: 290,
        y: 160,
        cpu: 72,
        mem: 68,
        latency: 280,
        errors: 3.4,
        uptime: '99.45%',
        upstream: ['CI-CDN-008'],
        downstream: ['CI-AUTH-004', 'CI-PAY-003'],
        activeIncidents: ['INC-9045']
      },
      {
        id: 'CI-AUTH-004',
        name: 'Auth0 & JWT Token Service',
        tier: 'Service',
        type: 'Authentication Microservice',
        health: 'degraded',
        team: '@security-secops',
        provider: 'K8s Cluster - auth-ns',
        x: 540,
        y: 80,
        cpu: 64,
        mem: 55,
        latency: 850,
        errors: 4.1,
        uptime: '99.12%',
        upstream: ['CI-INGRESS-005'],
        downstream: ['CI-CACHE-002'],
        activeIncidents: ['INC-9046']
      },
      {
        id: 'CI-PAY-003',
        name: 'Payment Gateway Service',
        tier: 'Service',
        type: 'Fintech Processing Engine',
        health: 'critical',
        team: '@payment-platform',
        provider: 'K8s Cluster - payments-ns',
        x: 540,
        y: 260,
        cpu: 89,
        mem: 82,
        latency: 1420,
        errors: 22.4,
        uptime: '97.80%',
        upstream: ['CI-INGRESS-005'],
        downstream: ['CI-DB-001', 'CI-CACHE-002', 'CI-KAFKA-007'],
        activeIncidents: ['INC-9043']
      },
      {
        id: 'CI-CACHE-002',
        name: 'Redis Session & Cache',
        tier: 'Data',
        type: 'In-Memory Cache Cluster',
        health: 'degraded',
        team: '@database-ops',
        provider: 'AWS ElastiCache Redis 7.0',
        x: 800,
        y: 80,
        cpu: 76,
        mem: 88,
        latency: 48,
        errors: 2.1,
        uptime: '98.90%',
        upstream: ['CI-AUTH-004', 'CI-PAY-003'],
        downstream: [],
        activeIncidents: ['INC-9044']
      },
      {
        id: 'CI-DB-001',
        name: 'PostgreSQL Primary (us-east-1)',
        tier: 'Data',
        type: 'Relational Database Aurora',
        health: 'critical',
        team: '@database-ops',
        provider: 'AWS RDS Aurora PostgreSQL 16.2',
        x: 800,
        y: 260,
        cpu: 98,
        mem: 88,
        latency: 1480,
        errors: 18.6,
        uptime: '98.42%',
        upstream: ['CI-PAY-003'],
        downstream: ['CI-K8S-006'],
        activeIncidents: ['INC-9042']
      },
      {
        id: 'CI-KAFKA-007',
        name: 'Kafka Order Event Bus',
        tier: 'Data',
        type: 'Message Streaming Bus',
        health: 'degraded',
        team: '@payment-platform',
        provider: 'Confluent Cloud (AWS us-east-1)',
        x: 800,
        y: 420,
        cpu: 58,
        mem: 62,
        latency: 120,
        errors: 1.2,
        uptime: '99.50%',
        upstream: ['CI-PAY-003'],
        downstream: ['CI-K8S-006'],
        activeIncidents: ['INC-9048']
      },
      {
        id: 'CI-K8S-006',
        name: 'EKS Core Cluster (us-east-1)',
        tier: 'Cloud',
        type: 'Kubernetes Infrastructure',
        health: 'healthy',
        team: '@cloud-infra',
        provider: 'AWS Elastic Kubernetes Service',
        x: 1040,
        y: 260,
        cpu: 48,
        mem: 65,
        latency: 22,
        errors: 0.05,
        uptime: '99.98%',
        upstream: ['CI-DB-001', 'CI-KAFKA-007'],
        downstream: [],
        activeIncidents: ['INC-9047']
      }
    ],

    // Active Incidents Portfolio (Zoho SDP & GLPI Schema)
    incidents: [
      {
        id: 'INC-9042',
        title: 'PostgreSQL Lock Contention & max_connections Exhaustion',
        description: 'Exclusive lock contention on table `order_transactions` caused by unindexed batch vacuum. Connection pool has reached 98% capacity, causing cascading 504 gateway timeouts across checkout API.',
        ci: 'CI-DB-001',
        ciName: 'PostgreSQL Primary (us-east-1)',
        category: 'Database & Storage',
        subcategory: 'PostgreSQL Aurora',
        item: 'Deadlock / Lock Contention',
        impact: 'Enterprise',
        urgency: 'Critical',
        priority: 'P1',
        status: 'IN_PROGRESS',
        team: 'Database-Ops',
        caller: 'alex.rivera@opennow.io',
        createdAt: '18 minutes ago',
        slaSecondsRemaining: 1440,
        slaInitialSeconds: 3600,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 0,
        aiTriageDone: true,
        aiConfidence: '99.2%',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'Alex Rivera (Lead SRE)',
            hours: 1,
            minutes: 15,
            rate: 150,
            cost: 187.50,
            isBillable: true,
            description: 'Analyzed pg_stat_activity query locks, identified rogue vacuum on order_transactions.',
            loggedAt: '14m ago'
          },
          {
            id: 'WL-2',
            technician: 'David Chen (DBA)',
            hours: 0,
            minutes: 45,
            rate: 130,
            cost: 97.50,
            isBillable: true,
            description: 'Prepared PgBouncer connection drain script and monitored connection count drop.',
            loggedAt: '8m ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Terminate blocking vacuum worker holding RowExclusiveLock',
            assignee: 'David Chen (DBA)',
            completed: true,
            completedAt: '12m ago'
          },
          {
            id: 'SUB-2',
            title: 'Scale out PgBouncer pooler to 6 replicas in database namespace',
            assignee: 'Alex Rivera (SRE)',
            completed: true,
            completedAt: '6m ago'
          },
          {
            id: 'SUB-3',
            title: 'Validate checkout 504 error rate < 0.05% on APM dashboard',
            assignee: 'Alex Rivera (SRE)',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '18m ago', user: 'Sentinel-AI', text: 'Auto-detected metric anomaly: PostgreSQL active connection spikes > 490/500.', isAi: true },
          { time: '14m ago', user: 'Alex Rivera (SRE)', text: 'Acknowledged incident. Paged @database-ops secondary on-call.' },
          { time: '8m ago', user: 'TriageBot', text: 'AI Root Cause Analysis completed: 3 long-running transactions holding RowExclusiveLock on order_transactions.', isAi: true }
        ]
      },
      {
        id: 'INC-9043',
        title: 'Payment Gateway Stripe Webhook 504 Timeout',
        description: 'Stripe charge authorization webhooks are failing with HTTP 504. Ingress proxy dropping requests exceeding 3000ms threshold. Customer purchases currently hanging at 3DS verification.',
        ci: 'CI-PAY-003',
        ciName: 'Payment Gateway Service',
        category: 'Software & Applications',
        subcategory: 'Payment Gateway',
        item: 'Webhook 504 Timeout',
        impact: 'Enterprise',
        urgency: 'High',
        priority: 'P1',
        status: 'NEW',
        team: 'Payment-Platform',
        caller: 'stripe-monitor@fintech.internal',
        createdAt: '6 minutes ago',
        slaSecondsRemaining: 1080,
        slaInitialSeconds: 3600,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 0,
        aiTriageDone: false,
        aiConfidence: '97.8%',
        worklogs: [],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Inspect Kong API Gateway ingress 504 error logs',
            assignee: 'Alex Rivera (SRE)',
            completed: false,
            completedAt: null
          },
          {
            id: 'SUB-2',
            title: 'Increase upstream timeout from 3000ms to 6000ms temporarily',
            assignee: 'Unassigned',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '6m ago', user: 'Webhook-Sentinel', text: 'Error rate breach: 22.4% non-200 responses on /v1/webhooks/stripe.', isAi: true },
          { time: '3m ago', user: 'Alex Rivera', text: 'Auto-escalated to P1 severity based on SLA countdown.' }
        ]
      },
      {
        id: 'INC-9044',
        title: 'Redis Session Cache Memory Pressure & Key Eviction Cascade',
        description: 'Redis cluster memory consumption spiked to 88% due to unexpired auth tokens. Key eviction policy volatile-lru is shedding active user sessions, leading to forced re-logins.',
        ci: 'CI-CACHE-002',
        ciName: 'Redis Session & Cache',
        category: 'Database & Storage',
        subcategory: 'Redis Cache',
        item: 'Memory Pressure / OOM Eviction',
        impact: 'Department',
        urgency: 'High',
        priority: 'P2',
        status: 'IN_PROGRESS',
        team: 'SRE-Core',
        caller: 'cloudwatch-alarm@aws.amazon.com',
        createdAt: '42 minutes ago',
        slaSecondsRemaining: 6300,
        slaInitialSeconds: 14400,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 120,
        aiTriageDone: true,
        aiConfidence: '96.5%',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'David Chen (DBA)',
            hours: 1,
            minutes: 0,
            rate: 130,
            cost: 130.00,
            isBillable: true,
            description: 'Ran volatile-lru eviction verification; identified stale JWT keys without TTL.',
            loggedAt: '25m ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Execute SCAN script to purge orphaned tokens with zero TTL',
            assignee: 'David Chen (DBA)',
            completed: true,
            completedAt: '20m ago'
          },
          {
            id: 'SUB-2',
            title: 'Apply maxmemory-policy allkeys-lru on replica nodes',
            assignee: 'David Chen (DBA)',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '42m ago', user: 'CloudWatch Sentinel', text: 'Memory pressure alarm fired on ElastiCache node redis-001.', isAi: true },
          { time: '25m ago', user: 'David Chen', text: 'Triggered safe keyspace scan. Identified expired JWTs not respecting TTL.' }
        ]
      },
      {
        id: 'INC-9045',
        title: 'Kong Ingress TLS Wildcard Cert Auto-Renewal ACME Failure',
        description: 'Let\'s Encrypt DNS-01 challenge timed out due to AWS Route53 rate limiting. Ingress TLS certificate will expire in 36 hours if not forcefully renewed.',
        ci: 'CI-INGRESS-005',
        ciName: 'Kong API Gateway',
        category: 'Cloud & Infrastructure',
        subcategory: 'API Gateway (Kong)',
        item: 'TLS Certificate Auto-Renewal Failure',
        impact: 'Department',
        urgency: 'High',
        priority: 'P2',
        status: 'ON_HOLD',
        team: 'Cloud-Infra',
        caller: 'cert-manager@k8s.internal',
        createdAt: '1 hour ago',
        slaSecondsRemaining: 7800,
        slaInitialSeconds: 14400,
        isPaused: true,
        holdReason: 'Pending Vendor',
        holdNotes: 'Awaiting AWS Route53 DNS propagation and SecOps IAM permissions for cert-manager role.',
        totalPausedSeconds: 1840,
        aiTriageDone: true,
        aiConfidence: '98.1%',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'Sarah Lin (Cloud Infra)',
            hours: 0,
            minutes: 40,
            rate: 120,
            cost: 80.00,
            isBillable: false,
            description: 'Investigated cert-manager ACME challenge timeout. Traced to missing route53:ChangeResourceRecordSets IAM role.',
            loggedAt: '35m ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Request emergency IAM trust policy update from SecOps',
            assignee: 'Sarah Lin (Cloud Infra)',
            completed: true,
            completedAt: '30m ago'
          },
          {
            id: 'SUB-2',
            title: 'Retry manual DNS-01 verification via cert-manager CLI',
            assignee: 'Sarah Lin (Cloud Infra)',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '1h ago', user: 'Cert-Manager', text: 'ACME challenge failed for *.api.opennow.io', isAi: true },
          { time: '30m ago', user: 'Sarah Lin', text: 'Placed on hold: [Pending Vendor]. Awaiting Route53 IAM update. SLA clock paused.' }
        ]
      },
      {
        id: 'INC-9046',
        title: 'Auth0 JWT Verification Signature Latency Spike (p99 > 850ms)',
        description: 'Intermittent latency degradation in JWKS key retrieval from Auth0 tenant endpoint. Causing 10-15% slow requests on authenticated REST calls.',
        ci: 'CI-AUTH-004',
        ciName: 'Auth0 & JWT Token Service',
        category: 'Software & Applications',
        subcategory: 'Auth & Identity (Auth0)',
        item: 'JWKS Key Retrieval Latency',
        impact: 'Department',
        urgency: 'High',
        priority: 'P2',
        status: 'IN_PROGRESS',
        team: 'Security-SecOps',
        caller: 'tracing-jaeger@opennow.io',
        createdAt: '1.5 hours ago',
        slaSecondsRemaining: 11700,
        slaInitialSeconds: 14400,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 0,
        aiTriageDone: true,
        aiConfidence: '94.0%',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'Alex Rivera (SRE)',
            hours: 0,
            minutes: 30,
            rate: 150,
            cost: 75.00,
            isBillable: true,
            description: 'Enabled in-memory local caching of JWKS public keys with 60m TTL.',
            loggedAt: '50m ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Deploy node-jwks-rsa client caching configuration patch',
            assignee: 'Alex Rivera (SRE)',
            completed: true,
            completedAt: '45m ago'
          },
          {
            id: 'SUB-2',
            title: 'Monitor p99 latency curve on Datadog APM dashboard',
            assignee: 'Alex Rivera (SRE)',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '1.5h ago', user: 'APM Jaeger', text: 'p99 latency threshold breached: 850ms.', isAi: true }
        ]
      },
      {
        id: 'INC-9047',
        title: 'EKS Worker Node Group Disk IOPS Throttling (gp3 burst credit)',
        description: 'Worker nodes running logging agent fluent-bit exhausted burst IOPS credits. Node status healthy but log collection latency increased by 180s.',
        ci: 'CI-K8S-006',
        ciName: 'EKS Core Cluster (us-east-1)',
        category: 'Cloud & Infrastructure',
        subcategory: 'Kubernetes Cluster (EKS)',
        item: 'Worker Node OOM / NotReady',
        impact: 'Single User',
        urgency: 'High',
        priority: 'P3',
        status: 'NEW',
        team: 'Cloud-Infra',
        caller: 'prometheus@k8s.opennow.io',
        createdAt: '2 hours ago',
        slaSecondsRemaining: 21600,
        slaInitialSeconds: 28800,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 0,
        aiTriageDone: false,
        aiConfidence: '91.2%',
        worklogs: [],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Switch gp3 volume baseline IOPS from 3,000 to 6,000 in Terraform',
            assignee: 'Sarah Lin (Cloud Infra)',
            completed: false,
            completedAt: null
          }
        ],
        timeline: [
          { time: '2h ago', user: 'Prometheus AlertManager', text: 'NodeFilesystemSpaceFillingUp triggered for node-pool-gp3.', isAi: true }
        ]
      },
      {
        id: 'INC-9048',
        title: 'Kafka Consumer Group Rebalance Latency on Order Stream',
        description: 'Consumer lag in consumer group `order-settlement-worker` reached 4,800 messages. Worker pod was OOMKilled and triggered partition reassignment.',
        ci: 'CI-KAFKA-007',
        ciName: 'Kafka Order Event Bus',
        category: 'Database & Storage',
        subcategory: 'Kafka Event Bus',
        item: 'Consumer Group Lag Breach',
        impact: 'Department',
        urgency: 'Medium',
        priority: 'P3',
        status: 'IN_PROGRESS',
        team: 'Payment-Platform',
        caller: 'kafka-exporter@monitoring.internal',
        createdAt: '3 hours ago',
        slaSecondsRemaining: 18000,
        slaInitialSeconds: 28800,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 0,
        aiTriageDone: true,
        aiConfidence: '93.4%',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'Alex Rivera (SRE)',
            hours: 1,
            minutes: 0,
            rate: 150,
            cost: 150.00,
            isBillable: true,
            description: 'Identified consumer worker pod OOMKill due to heap ceiling. Bumped memory limit to 2Gi.',
            loggedAt: '1.5h ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Adjust max.poll.records to 250 in consumer configuration',
            assignee: 'Alex Rivera (SRE)',
            completed: true,
            completedAt: '1h ago'
          }
        ],
        timeline: [
          { time: '3h ago', user: 'Kafka Monitor', text: 'Consumer lag spiked above 4000 messages.', isAi: true }
        ]
      },
      {
        id: 'INC-9049',
        title: 'Cloudflare HTTP/3 Fallback Variance in South America PoP',
        description: 'QUIC protocol UDP drops in Sao Paulo edge location causing 2.4% fallback rate to HTTP/2. Minimal customer impact observed.',
        ci: 'CI-CDN-008',
        ciName: 'Cloudflare Global Edge',
        category: 'Cloud & Infrastructure',
        subcategory: 'Edge & CDN (Cloudflare)',
        item: 'HTTP/3 QUIC UDP Fallback',
        impact: 'Single User',
        urgency: 'Low',
        priority: 'P4',
        status: 'RESOLVED',
        team: 'SRE-Core',
        caller: 'cloudflare-api@bot.internal',
        createdAt: '5 hours ago',
        slaSecondsRemaining: 0,
        slaInitialSeconds: 86400,
        isPaused: false,
        holdReason: '',
        holdNotes: '',
        totalPausedSeconds: 320,
        resolutionCode: 'Workaround Applied',
        rootCause: 'Upstream carrier transit peering between Sao Paulo and Rio de Janeiro had MTU mismatch dropping UDP 443 packets.',
        preventiveAction: 'Updated BGP Anycast route map weights to prefer direct IXP peering.',
        isFcr: true,
        resolvedAt: '4 hours ago',
        worklogs: [
          {
            id: 'WL-1',
            technician: 'Alex Rivera (SRE)',
            hours: 0,
            minutes: 45,
            rate: 150,
            cost: 112.50,
            isBillable: true,
            description: 'Traced UDP MTU packet loss to transit peer; rerouted traffic via Anycast control plane.',
            loggedAt: '4h ago'
          }
        ],
        subtasks: [
          {
            id: 'SUB-1',
            title: 'Run traceroute and MTU path discovery to GRU edge',
            assignee: 'Alex Rivera (SRE)',
            completed: true,
            completedAt: '4.5h ago'
          },
          {
            id: 'SUB-2',
            title: 'Verify HTTP/3 handshake success rate in Cloudflare analytics',
            assignee: 'Alex Rivera (SRE)',
            completed: true,
            completedAt: '4h ago'
          }
        ],
        timeline: [
          { time: '5h ago', user: 'Cloudflare Bot', text: 'Detected UDP packet drop in GRU PoP.', isAi: true },
          { time: '4h ago', user: 'Alex Rivera', text: 'Resolved incident: [Workaround Applied]. FCR: Yes. Root Cause: Upstream MTU mismatch.' }
        ]
      }
    ],

    // Real-Time AI Autonomous SRE Log Stream
    aiEvents: [
      { time: '14:28:12', agent: 'Sentinel-Triage AI', msg: 'Correlated 14 CloudWatch alerts to root CI: PostgreSQL Primary (CI-DB-001).' },
      { time: '14:26:44', agent: 'Blast Radius Engine', msg: 'Recomputed graph blast radius: 4 services affected, $1,420/min exposure.' },
      { time: '14:22:05', agent: 'Runbook Synthesizer', msg: 'Generated emergency connection drain script for PgBouncer.' },
      { time: '14:18:30', agent: 'Sentinel-Triage AI', msg: 'Auto-escalated INC-9042 from P2 to P1 Critical based on SLA velocity.' }
    ]
  };

  // =========================================================================
  // TOP 10 NATIVE MIGRATION PLATFORM DATASETS
  // =========================================================================

  const TOP_10_PLATFORMS = {
    servicenow: {
      name: 'ServiceNow',
      source: 'ServiceNow Tokyo / Utah Instance Export',
      entity: 'Full sys_id XML / JSON Table API',
      qualityScore: '98/100',
      mappedCount: '12 / 12 (100%)',
      recordCount: '50 Incidents • 12 CIs',
      strategy: 'Automated translation of ServiceNow `u_urgency=1` mapped to OpenNow `P1 Critical`. Automated regex normalized caller email domains and mapped `cmdb_ci` relations directly to your live CMDB topology with 0 orphaned records.',
      tables: {
        tasks: [
          { source: 'sys_id', target: 'id (PK)', type: 'GUID / String', fk: 'Primary Key', sample: '9c5f812a0f812110b...' },
          { source: 'number', target: 'legacy_key', type: 'String', fk: 'None', sample: 'INC0089201' },
          { source: 'short_description', target: 'title', type: 'String (255)', fk: 'None', sample: 'PostgreSQL Lock Contention on checkout' },
          { source: 'description', target: 'description', type: 'Text', fk: 'None', sample: 'Exclusive lock contention on table order_transactions...' },
          { source: 'priority / urgency', target: 'priority', type: 'Enum (P1-P4)', fk: 'Normalized', sample: '1 - Critical -> P1' },
          { source: 'cmdb_ci', target: 'ci', type: 'Reference', fk: 'FK -> cmdb_ci.sys_id', sample: 'pg-prod-us-east-1 -> CI-DB-001' },
          { source: 'assignment_group', target: 'team', type: 'Reference', fk: 'FK -> sys_user_group', sample: 'Database Support -> Database-Ops' },
          { source: 'caller_id', target: 'caller', type: 'Reference', fk: 'FK -> sys_user.sys_id', sample: 'sre-oncall@opennow.io' },
          { source: 'state', target: 'status', type: 'Integer -> Enum', fk: 'Normalized', sample: '2 (In Progress) -> IN_PROGRESS' }
        ],
        users: [
          { source: 'sys_id', target: 'user_id', type: 'GUID', fk: 'Primary Key', sample: '62826bf0371020004...' },
          { source: 'user_name', target: 'username', type: 'String', fk: 'None', sample: 'alex.rivera' },
          { source: 'email', target: 'email', type: 'Email', fk: 'None', sample: 'alex.rivera@opennow.io' },
          { source: 'first_name', target: 'first_name', type: 'String', fk: 'None', sample: 'Alex' },
          { source: 'last_name', target: 'last_name', type: 'String', fk: 'None', sample: 'Rivera' },
          { source: 'title', target: 'role', type: 'String', fk: 'None', sample: 'Lead SRE Architect' }
        ],
        groups: [
          { source: 'sys_id', target: 'team_id', type: 'GUID', fk: 'Primary Key', sample: '8a4dde73c61122780...' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Database-Ops' },
          { source: 'description', target: 'description', type: 'String', fk: 'None', sample: 'Database Reliability & Aurora DBA team' },
          { source: 'manager', target: 'lead_user_id', type: 'Reference', fk: 'FK -> sys_user.sys_id', sample: 'David Chen' }
        ],
        cmdb: [
          { source: 'sys_id', target: 'ci_id', type: 'GUID', fk: 'Primary Key', sample: '2b4c81010f812110c...' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'PostgreSQL Primary (us-east-1)' },
          { source: 'sys_class_name', target: 'tier', type: 'String', fk: 'None', sample: 'cmdb_ci_database -> Data' },
          { source: 'operational_status', target: 'health', type: 'Integer', fk: 'Normalized', sample: '1 -> healthy, 2 -> degraded' }
        ],
        relations: [
          { source: 'parent', target: 'source_ci_id', type: 'Reference', fk: 'FK -> cmdb_ci', sample: 'CI-PAY-003' },
          { source: 'child', target: 'target_ci_id', type: 'Reference', fk: 'FK -> cmdb_ci', sample: 'CI-DB-001' },
          { source: 'type', target: 'relationship_type', type: 'String', fk: 'None', sample: 'Depends on::Used by' }
        ],
        journal: [
          { source: 'element_id', target: 'ticket_id', type: 'Reference', fk: 'FK -> incident.sys_id', sample: 'INC-9042' },
          { source: 'value', target: 'text', type: 'Text', fk: 'None', sample: 'Vacuum batch killed. Locking mitigated.' },
          { source: 'sys_created_by', target: 'user', type: 'String', fk: 'None', sample: 'alex.rivera' },
          { source: 'sys_created_on', target: 'time', type: 'Timestamp', fk: 'None', sample: '2026-10-11 14:14:00' }
        ]
      },
      mappings: [
        { source: 'sys_id', target: 'ticket_id', confidence: '99%', sample: 'INC0089201' },
        { source: 'short_description', target: 'title', confidence: '99%', sample: 'PostgreSQL Lock Contention on checkout' },
        { source: 'description', target: 'description', confidence: '98%', sample: 'Exclusive lock contention on table order_transactions...' },
        { source: 'u_urgency / priority', target: 'priority (P1-P4)', confidence: '97%', sample: '1 - Critical -> P1' },
        { source: 'cmdb_ci', target: 'ci_node_id', confidence: '96%', sample: 'pg-prod-us-east-1 -> CI-DB-001' },
        { source: 'assignment_group', target: 'team', confidence: '95%', sample: 'Database Support -> Database-Ops' },
        { source: 'caller_id.email', target: 'caller', confidence: '99%', sample: 'sre-oncall@opennow.io' },
        { source: 'state', target: 'status (Normalized)', confidence: '98%', sample: '2 (In Progress) -> IN_PROGRESS' }
      ],
      previewRecords: [
        { id: 'SNOW-8921', priority: 'P1', title: 'PostgreSQL Lock Contention on checkout', ci: 'CI-DB-001', team: 'Database-Ops' },
        { id: 'SNOW-8922', priority: 'P2', title: 'Payment Gateway webhook failure', ci: 'CI-PAY-003', team: 'Payment-Platform' },
        { id: 'SNOW-8923', priority: 'P3', title: 'Kafka Consumer Group Rebalance Timeout', ci: 'CI-KAFKA-007', team: 'Payment-Platform' }
      ]
    },

    jira: {
      name: 'Jira Service Management',
      source: 'Jira Service Management Cloud REST Export',
      entity: 'ITSM Issues, Assets & Workflows',
      qualityScore: '97/100',
      mappedCount: '10 / 10 (100%)',
      recordCount: '42 Issues • 8 Assets',
      strategy: 'Transformed Jira issue types (Incident/Bug) into normalized OpenNow severity matrix. Linked Jira Assets object schema entries to OpenNow CMDB nodes.',
      tables: {
        tasks: [
          { source: 'issue_key', target: 'id (PK)', type: 'String', fk: 'Primary Key', sample: 'OPS-4412' },
          { source: 'summary', target: 'title', type: 'String', fk: 'None', sample: 'Redis session store memory alert' },
          { source: 'description', target: 'description', type: 'Text', fk: 'None', sample: 'Redis cluster memory pressure > 85%...' },
          { source: 'priority.name', target: 'priority', type: 'Enum', fk: 'Normalized', sample: 'Highest -> P1, High -> P2' },
          { source: 'components[0].name', target: 'ci', type: 'Reference', fk: 'FK -> Assets', sample: 'Redis Cache -> CI-CACHE-002' },
          { source: 'assignee.displayName', target: 'team', type: 'Reference', fk: 'FK -> Team', sample: 'SRE Core Team -> SRE-Core' }
        ],
        users: [
          { source: 'accountId', target: 'user_id', type: 'String', fk: 'Primary Key', sample: 'qm:892019a...' },
          { source: 'displayName', target: 'name', type: 'String', fk: 'None', sample: 'David Chen' },
          { source: 'emailAddress', target: 'email', type: 'Email', fk: 'None', sample: 'david.chen@opennow.io' }
        ],
        groups: [
          { source: 'projectRole', target: 'team_id', type: 'String', fk: 'Primary Key', sample: 'ROLE_SRE' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'SRE-Core' }
        ],
        cmdb: [
          { source: 'workspaceId/objectKey', target: 'ci_id', type: 'String', fk: 'Primary Key', sample: 'ASSET-102' },
          { source: 'label', target: 'name', type: 'String', fk: 'None', sample: 'Redis Session Cache' }
        ],
        relations: [
          { source: 'inwardIssue', target: 'source_ci_id', type: 'Reference', fk: 'FK -> Assets', sample: 'CI-AUTH-004' },
          { source: 'outwardIssue', target: 'target_ci_id', type: 'Reference', fk: 'FK -> Assets', sample: 'CI-CACHE-002' }
        ],
        journal: [
          { source: 'comments.author', target: 'user', type: 'String', fk: 'None', sample: 'david.chen' },
          { source: 'comments.body', target: 'text', type: 'Text', fk: 'None', sample: 'Keyspace scan executed.' }
        ]
      },
      mappings: [
        { source: 'issue_key', target: 'ticket_id', confidence: '99%', sample: 'OPS-4412' },
        { source: 'summary', target: 'title', confidence: '99%', sample: 'Redis session store memory alert' },
        { source: 'description', target: 'description', confidence: '97%', sample: 'Redis cluster memory pressure > 85%...' },
        { source: 'priority.name', target: 'priority', confidence: '98%', sample: 'Highest -> P1, High -> P2' },
        { source: 'components[0].name', target: 'ci_node_id', confidence: '94%', sample: 'Cache Service -> CI-CACHE-002' },
        { source: 'reporter.emailAddress', target: 'caller', confidence: '99%', sample: 'devops-lead@company.com' }
      ],
      previewRecords: [
        { id: 'JIRA-4412', priority: 'P2', title: 'Redis session store memory alert', ci: 'CI-CACHE-002', team: 'SRE-Core' },
        { id: 'JIRA-4413', priority: 'P1', title: 'Kong Ingress TLS cert auto-renewal failed', ci: 'CI-INGRESS-005', team: 'Cloud-Infra' },
        { id: 'JIRA-4414', priority: 'P3', title: 'EKS gp3 disk IOPS burst credit exhausted', ci: 'CI-K8S-006', team: 'Cloud-Infra' }
      ]
    },

    zendesk: {
      name: 'Zendesk',
      source: 'Zendesk Support JSON API Export',
      entity: 'Tickets, Users & Organizations',
      qualityScore: '96/100',
      mappedCount: '9 / 9 (100%)',
      recordCount: '64 Tickets • 15 Orgs',
      strategy: 'Mapped Zendesk Organizations and custom ticket drop-down fields to CMDB Configuration Items. Standardized Urgent/High priorities into ITIL P1/P2.',
      tables: {
        tasks: [
          { source: 'id', target: 'id (PK)', type: 'Integer', fk: 'Primary Key', sample: '381920' },
          { source: 'subject', target: 'title', type: 'String', fk: 'None', sample: 'Checkout gateway timing out for customers' },
          { source: 'description', target: 'description', type: 'Text', fk: 'None', sample: 'Customers reporting hung payment screens...' },
          { source: 'priority', target: 'priority', type: 'String', fk: 'Normalized', sample: 'urgent -> P1, high -> P2' },
          { source: 'organization_id', target: 'ci', type: 'Reference', fk: 'FK -> Org/CI', sample: 'Org-Fintech -> CI-PAY-003' }
        ],
        users: [
          { source: 'id', target: 'user_id', type: 'Integer', fk: 'Primary Key', sample: '109281' },
          { source: 'email', target: 'email', type: 'Email', fk: 'None', sample: 'customer-ops@client.com' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Support Team' }
        ],
        groups: [
          { source: 'group_id', target: 'team_id', type: 'Integer', fk: 'Primary Key', sample: '89102' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Payment-Platform' }
        ],
        cmdb: [
          { source: 'org_id', target: 'ci_id', type: 'Integer', fk: 'Primary Key', sample: '44102' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Payment Gateway Service' }
        ],
        relations: [
          { source: 'parent_org_id', target: 'source_ci_id', type: 'Reference', fk: 'FK -> Org', sample: 'CI-INGRESS-005' },
          { source: 'child_org_id', target: 'target_ci_id', type: 'Reference', fk: 'FK -> Org', sample: 'CI-PAY-003' }
        ],
        journal: [
          { source: 'audits.events.body', target: 'text', type: 'Text', fk: 'None', sample: 'Investigating payment proxy timeout.' },
          { source: 'audits.created_at', target: 'time', type: 'Timestamp', fk: 'None', sample: '2026-10-11 13:45:00' }
        ]
      },
      mappings: [
        { source: 'id', target: 'ticket_id', confidence: '99%', sample: 'ZD-381920' },
        { source: 'subject', target: 'title', confidence: '98%', sample: 'Checkout gateway timing out' },
        { source: 'priority', target: 'priority', confidence: '98%', sample: 'urgent -> P1' },
        { source: 'requester.email', target: 'caller', confidence: '99%', sample: 'customer-ops@client.com' }
      ],
      previewRecords: [
        { id: 'ZD-3819', priority: 'P1', title: 'Checkout gateway timing out for customers', ci: 'CI-PAY-003', team: 'Payment-Platform' },
        { id: 'ZD-3820', priority: 'P2', title: 'Single Sign-On login failures on portal', ci: 'CI-AUTH-004', team: 'Security-SecOps' },
        { id: 'ZD-3821', priority: 'P3', title: 'Intermittent rate-limit trigger on public API', ci: 'CI-INGRESS-005', team: 'Cloud-Infra' }
      ]
    },

    freshservice: {
      name: 'Freshservice',
      source: 'Freshservice Enterprise XML / JSON Dump',
      entity: 'Incidents & CMDB Assets',
      qualityScore: '97/100',
      mappedCount: '10 / 10 (100%)',
      recordCount: '38 Tickets • 14 Assets',
      strategy: 'Extracted Freshservice Asset Management CMDB entities and relationship tree. Mapped Department and Agent Group assignments to OpenNow teams.',
      tables: {
        tasks: [
          { source: 'display_id', target: 'id (PK)', type: 'Integer', fk: 'Primary Key', sample: 'FS-9841' },
          { source: 'subject', target: 'title', type: 'String', fk: 'None', sample: 'Kafka stream buffer saturation' },
          { source: 'description_text', target: 'description', type: 'Text', fk: 'None', sample: 'Event partition lag exceeding threshold...' },
          { source: 'priority (1-4)', target: 'priority', type: 'Integer', fk: 'Normalized', sample: '1 -> P1, 2 -> P2' },
          { source: 'asset_id', target: 'ci', type: 'Reference', fk: 'FK -> CMDB', sample: 'CI-KAFKA-007' }
        ],
        users: [
          { source: 'id', target: 'user_id', type: 'Integer', fk: 'Primary Key', sample: '2019' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Sarah Lin' },
          { source: 'email', target: 'email', type: 'Email', fk: 'None', sample: 'sarah.lin@opennow.io' }
        ],
        groups: [
          { source: 'group_id', target: 'team_id', type: 'Integer', fk: 'Primary Key', sample: '702' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Payment-Platform' }
        ],
        cmdb: [
          { source: 'display_id', target: 'ci_id', type: 'String', fk: 'Primary Key', sample: 'CI-KAFKA-007' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Kafka Order Event Bus' }
        ],
        relations: [
          { source: 'parent_asset', target: 'source_ci_id', type: 'Reference', fk: 'FK -> Assets', sample: 'CI-PAY-003' },
          { source: 'child_asset', target: 'target_ci_id', type: 'Reference', fk: 'FK -> Assets', sample: 'CI-KAFKA-007' }
        ],
        journal: [
          { source: 'conversations.body_text', target: 'text', type: 'Text', fk: 'None', sample: 'Broker nodes scaled up.' }
        ]
      },
      mappings: [
        { source: 'display_id', target: 'ticket_id', confidence: '99%', sample: 'FS-9841' },
        { source: 'subject', target: 'title', confidence: '98%', sample: 'Kafka stream buffer saturation' },
        { source: 'priority', target: 'priority', confidence: '99%', sample: '2 -> P2' }
      ],
      previewRecords: [
        { id: 'FS-9841', priority: 'P2', title: 'Kafka stream buffer saturation on order stream', ci: 'CI-KAFKA-007', team: 'Payment-Platform' },
        { id: 'FS-9842', priority: 'P1', title: 'RDS Aurora write latency spike', ci: 'CI-DB-001', team: 'Database-Ops' },
        { id: 'FS-9843', priority: 'P3', title: 'Kong ingress proxy reload restart cycle', ci: 'CI-INGRESS-005', team: 'Cloud-Infra' }
      ]
    },

    bmc: {
      name: 'BMC Helix / Remedy',
      source: 'BMC Remedy ARS ARX / XML Data Extract',
      entity: 'HPD:Help Desk & BMC.ASSET:BaseElement',
      qualityScore: '95/100',
      mappedCount: '11 / 11 (100%)',
      recordCount: '48 Incidents • 18 CIs',
      strategy: 'Parsed Remedy ARS schema forms, normalizing CTM:People callers and mapping BMC.ASSET:BaseElement CI instances directly to OpenNow CMDB nodes.',
      tables: {
        tasks: [
          { source: 'Incident Number', target: 'id (PK)', type: 'String', fk: 'Primary Key', sample: 'INC0000049281' },
          { source: 'Detailed Decription', target: 'description', type: 'Text', fk: 'None', sample: 'Aurora database connections saturated...' },
          { source: 'Urgency / Impact', target: 'priority', type: 'String', fk: 'Normalized', sample: '1-Critical -> P1' },
          { source: 'CI+', target: 'ci', type: 'Reference', fk: 'FK -> BaseElement', sample: 'CI-DB-001' },
          { source: 'Assigned Group', target: 'team', type: 'String', fk: 'FK -> SupportGroup', sample: 'Database-Ops' }
        ],
        users: [
          { source: 'Person ID', target: 'user_id', type: 'String', fk: 'Primary Key', sample: 'PPL000109' },
          { source: 'Email Address', target: 'email', type: 'Email', fk: 'None', sample: 'remedy-admin@company.com' }
        ],
        groups: [
          { source: 'Support Group ID', target: 'team_id', type: 'String', fk: 'Primary Key', sample: 'SGP00021' },
          { source: 'Support Group Name', target: 'name', type: 'String', fk: 'None', sample: 'Database-Ops' }
        ],
        cmdb: [
          { source: 'ReconciliationIdentity', target: 'ci_id', type: 'String', fk: 'Primary Key', sample: 'CI-DB-001' },
          { source: 'Name', target: 'name', type: 'String', fk: 'None', sample: 'PostgreSQL Primary (us-east-1)' }
        ],
        relations: [
          { source: 'Source.ReconciliationIdentity', target: 'source_ci_id', type: 'Reference', fk: 'FK -> CMDB', sample: 'CI-PAY-003' },
          { source: 'Destination.ReconciliationIdentity', target: 'target_ci_id', type: 'Reference', fk: 'FK -> CMDB', sample: 'CI-DB-001' }
        ],
        journal: [
          { source: 'Work Log Submitter', target: 'user', type: 'String', fk: 'None', sample: 'remedy-admin' },
          { source: 'Detailed Description', target: 'text', type: 'Text', fk: 'None', sample: 'Cleared connection pool.' }
        ]
      },
      mappings: [
        { source: 'Incident Number', target: 'ticket_id', confidence: '99%', sample: 'INC0000049281' },
        { source: 'Description', target: 'title', confidence: '96%', sample: 'Postgres RDS Aurora lock exhaustion' },
        { source: 'Urgency', target: 'priority', confidence: '97%', sample: '1-Critical -> P1' }
      ],
      previewRecords: [
        { id: 'BMC-49281', priority: 'P1', title: 'Postgres RDS Aurora lock exhaustion', ci: 'CI-DB-001', team: 'Database-Ops' },
        { id: 'BMC-49282', priority: 'P2', title: 'Payment token decryption latency', ci: 'CI-AUTH-004', team: 'Security-SecOps' },
        { id: 'BMC-49283', priority: 'P3', title: 'Kubernetes core cluster memory warning', ci: 'CI-K8S-006', team: 'Cloud-Infra' }
      ]
    },

    salesforce: {
      name: 'Salesforce Service Cloud',
      source: 'Salesforce Case Object SOQL Export',
      entity: 'Case, Asset & FeedItem Objects',
      qualityScore: '98/100',
      mappedCount: '10 / 10 (100%)',
      recordCount: '55 Cases • 10 Assets',
      strategy: 'Extracted Salesforce Case records, resolving Contact callers, Queue routing to OpenNow assignment teams, and CaseComment thread histories.',
      tables: {
        tasks: [
          { source: 'CaseNumber', target: 'id (PK)', type: 'String', fk: 'Primary Key', sample: '00084920' },
          { source: 'Subject', target: 'title', type: 'String', fk: 'None', sample: 'Auth0 token verification latency > 850ms' },
          { source: 'Description', target: 'description', type: 'Text', fk: 'None', sample: 'Intermittent degradation in JWKS key retrieval...' },
          { source: 'Priority', target: 'priority', type: 'String', fk: 'Normalized', sample: 'Critical -> P1, High -> P2' },
          { source: 'AssetId', target: 'ci', type: 'Reference', fk: 'FK -> Asset', sample: 'CI-AUTH-004' }
        ],
        users: [
          { source: 'Contact.Id', target: 'user_id', type: 'String', fk: 'Primary Key', sample: '00382019...' },
          { source: 'Contact.Email', target: 'email', type: 'Email', fk: 'None', sample: 'lead-dev@company.com' }
        ],
        groups: [
          { source: 'Owner:Queue.Id', target: 'team_id', type: 'String', fk: 'Primary Key', sample: '00G82019...' },
          { source: 'Owner:Queue.Name', target: 'name', type: 'String', fk: 'None', sample: 'Security-SecOps' }
        ],
        cmdb: [
          { source: 'Asset.Id', target: 'ci_id', type: 'String', fk: 'Primary Key', sample: '02i8201...' },
          { source: 'Asset.Name', target: 'name', type: 'String', fk: 'None', sample: 'Auth0 & JWT Token Service' }
        ],
        relations: [
          { source: 'AssetRelationship.AssetId', target: 'source_ci_id', type: 'Reference', fk: 'FK -> Asset', sample: 'CI-INGRESS-005' },
          { source: 'AssetRelationship.RelatedAssetId', target: 'target_ci_id', type: 'Reference', fk: 'FK -> Asset', sample: 'CI-AUTH-004' }
        ],
        journal: [
          { source: 'CaseComment.CommentBody', target: 'text', type: 'Text', fk: 'None', sample: 'JWKS cache refreshed.' }
        ]
      },
      mappings: [
        { source: 'CaseNumber', target: 'ticket_id', confidence: '99%', sample: 'SF-00084920' },
        { source: 'Subject', target: 'title', confidence: '99%', sample: 'Auth0 token verification latency' },
        { source: 'Priority', target: 'priority', confidence: '98%', sample: 'High -> P2' }
      ],
      previewRecords: [
        { id: 'SF-84920', priority: 'P2', title: 'Auth0 token verification latency > 850ms', ci: 'CI-AUTH-004', team: 'Security-SecOps' },
        { id: 'SF-84921', priority: 'P1', title: 'Stripe webhook 504 timeout on purchase', ci: 'CI-PAY-003', team: 'Payment-Platform' },
        { id: 'SF-84922', priority: 'P3', title: 'Cloudflare edge TCP packet loss', ci: 'CI-CDN-008', team: 'SRE-Core' }
      ]
    },

    cherwell: {
      name: 'Cherwell / Ivanti',
      source: 'Cherwell Service Management JSON Dump',
      entity: 'CSM Relational Tables & CI Links',
      qualityScore: '96/100',
      mappedCount: '9 / 9 (100%)',
      recordCount: '36 Incidents • 11 ConfigItems',
      strategy: 'Translated Cherwell Business Objects (Incident, ConfigItem, TeamDef) into normalized OpenNow relational tables with verified FK references.',
      tables: {
        tasks: [
          { source: 'IncidentID', target: 'id (PK)', type: 'String', fk: 'Primary Key', sample: 'CHW-10928' },
          { source: 'ShortDescription', target: 'title', type: 'String', fk: 'None', sample: 'Redis session store memory alert' },
          { source: 'Priority', target: 'priority', type: 'String', fk: 'Normalized', sample: '1 -> P1, 2 -> P2' },
          { source: 'PrimaryCI', target: 'ci', type: 'Reference', fk: 'FK -> ConfigItem', sample: 'CI-CACHE-002' },
          { source: 'OwnedByTeam', target: 'team', type: 'String', fk: 'FK -> TeamDef', sample: 'SRE-Core' }
        ],
        users: [
          { source: 'CustomerRecID', target: 'user_id', type: 'String', fk: 'Primary Key', sample: 'REC-901' },
          { source: 'CustomerEmail', target: 'email', type: 'Email', fk: 'None', sample: 'caller@client.io' }
        ],
        groups: [
          { source: 'TeamDefID', target: 'team_id', type: 'String', fk: 'Primary Key', sample: 'TEAM-01' },
          { source: 'TeamName', target: 'name', type: 'String', fk: 'None', sample: 'SRE-Core' }
        ],
        cmdb: [
          { source: 'ConfigItemRecID', target: 'ci_id', type: 'String', fk: 'Primary Key', sample: 'CI-CACHE-002' },
          { source: 'CIName', target: 'name', type: 'String', fk: 'None', sample: 'Redis Session & Cache' }
        ],
        relations: [
          { source: 'ParentCI', target: 'source_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-AUTH-004' },
          { source: 'ChildCI', target: 'target_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-CACHE-002' }
        ],
        journal: [
          { source: 'IncidentHistory.Details', target: 'text', type: 'Text', fk: 'None', sample: 'Key eviction monitored.' }
        ]
      },
      mappings: [
        { source: 'IncidentID', target: 'ticket_id', confidence: '99%', sample: 'CHW-10928' },
        { source: 'ShortDescription', target: 'title', confidence: '98%', sample: 'Redis session store memory alert' },
        { source: 'Priority', target: 'priority', confidence: '97%', sample: '2 -> P2' }
      ],
      previewRecords: [
        { id: 'CHW-10928', priority: 'P2', title: 'Redis session store memory alert', ci: 'CI-CACHE-002', team: 'SRE-Core' },
        { id: 'CHW-10929', priority: 'P1', title: 'PostgreSQL Aurora max connection limit reached', ci: 'CI-DB-001', team: 'Database-Ops' },
        { id: 'CHW-10930', priority: 'P3', title: 'EKS cluster burst IOPS credit exhausted', ci: 'CI-K8S-006', team: 'Cloud-Infra' }
      ]
    },

    manageengine: {
      name: 'ManageEngine SDP',
      source: 'ManageEngine ServiceDesk Plus XML Export',
      entity: 'WorkOrder, CI & CIRelation Tables',
      qualityScore: '95/100',
      mappedCount: '10 / 10 (100%)',
      recordCount: '40 WorkOrders • 13 CIs',
      strategy: 'Reconciled ManageEngine WorkOrder items, CI inventory, and CIRelation graph edges into OpenNow CMDB schema.',
      tables: {
        tasks: [
          { source: 'WORKORDERID', target: 'id (PK)', type: 'Integer', fk: 'Primary Key', sample: 'WO-80192' },
          { source: 'TITLE', target: 'title', type: 'String', fk: 'None', sample: 'Kong Ingress TLS cert auto-renewal failed' },
          { source: 'PRIORITYID', target: 'priority', type: 'Integer', fk: 'Normalized', sample: '1 -> P1, 2 -> P2' },
          { source: 'ASSETID', target: 'ci', type: 'Reference', fk: 'FK -> CI', sample: 'CI-INGRESS-005' },
          { source: 'QUEUENAME', target: 'team', type: 'String', fk: 'FK -> Queue', sample: 'Cloud-Infra' }
        ],
        users: [
          { source: 'USERID', target: 'user_id', type: 'Integer', fk: 'Primary Key', sample: '3012' },
          { source: 'EMAILID', target: 'email', type: 'Email', fk: 'None', sample: 'sre-lead@company.com' }
        ],
        groups: [
          { source: 'QUEUEID', target: 'team_id', type: 'Integer', fk: 'Primary Key', sample: '501' },
          { source: 'QUEUENAME', target: 'name', type: 'String', fk: 'None', sample: 'Cloud-Infra' }
        ],
        cmdb: [
          { source: 'CIID', target: 'ci_id', type: 'Integer', fk: 'Primary Key', sample: '8101' },
          { source: 'CINAME', target: 'name', type: 'String', fk: 'None', sample: 'Kong API Gateway' }
        ],
        relations: [
          { source: 'SOURCE_CIID', target: 'source_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-CDN-008' },
          { source: 'DEST_CIID', target: 'target_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-INGRESS-005' }
        ],
        journal: [
          { source: 'WorkOrderNotes.NOTESTEXT', target: 'text', type: 'Text', fk: 'None', sample: 'Renewed certificate manually.' }
        ]
      },
      mappings: [
        { source: 'WORKORDERID', target: 'ticket_id', confidence: '99%', sample: 'ME-80192' },
        { source: 'TITLE', target: 'title', confidence: '98%', sample: 'Kong Ingress TLS cert auto-renewal failed' },
        { source: 'PRIORITYID', target: 'priority', confidence: '96%', sample: '2 -> P2' }
      ],
      previewRecords: [
        { id: 'ME-80192', priority: 'P2', title: 'Kong Ingress TLS cert auto-renewal failed', ci: 'CI-INGRESS-005', team: 'Cloud-Infra' },
        { id: 'ME-80193', priority: 'P1', title: 'Database deadlock during vacuum execution', ci: 'CI-DB-001', team: 'Database-Ops' },
        { id: 'ME-80194', priority: 'P3', title: 'Kafka event bus lag alert', ci: 'CI-KAFKA-007', team: 'Payment-Platform' }
      ]
    },

    glpi: {
      name: 'GLPI Open Source',
      source: 'GLPI ITIL MariaDB / JSON Dump',
      entity: 'glpi_tickets, glpi_items & Followups',
      qualityScore: '95/100',
      mappedCount: '9 / 9 (100%)',
      recordCount: '35 Tickets • 12 Items',
      strategy: 'Heuristic translation of GLPI multilingual schema. Converted glpi_items inventory directly to OpenNow CMDB nodes.',
      tables: {
        tasks: [
          { source: 'id', target: 'id (PK)', type: 'Integer', fk: 'Primary Key', sample: 'GLPI-1049' },
          { source: 'name', target: 'title', type: 'String', fk: 'None', sample: 'Auth0 JWT verification latency > 850ms' },
          { source: 'urgency', target: 'priority', type: 'Integer', fk: 'Normalized', sample: '5 -> P1, 4 -> P2' },
          { source: 'items_id', target: 'ci', type: 'Reference', fk: 'FK -> glpi_items', sample: 'CI-AUTH-004' },
          { source: 'groups_id', target: 'team', type: 'Reference', fk: 'FK -> glpi_groups', sample: 'Security-SecOps' }
        ],
        users: [
          { source: 'id', target: 'user_id', type: 'Integer', fk: 'Primary Key', sample: '44' },
          { source: 'name', target: 'username', type: 'String', fk: 'None', sample: 'glpi.tech' },
          { source: 'email', target: 'email', type: 'Email', fk: 'None', sample: 'glpi-tech@company.eu' }
        ],
        groups: [
          { source: 'id', target: 'team_id', type: 'Integer', fk: 'Primary Key', sample: '12' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Security-SecOps' }
        ],
        cmdb: [
          { source: 'id', target: 'ci_id', type: 'Integer', fk: 'Primary Key', sample: '104' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Auth0 & JWT Token Service' }
        ],
        relations: [
          { source: 'items_id_1', target: 'source_ci_id', type: 'Reference', fk: 'FK -> items', sample: 'CI-INGRESS-005' },
          { source: 'items_id_2', target: 'target_ci_id', type: 'Reference', fk: 'FK -> items', sample: 'CI-AUTH-004' }
        ],
        journal: [
          { source: 'glpi_itilfollowups.content', target: 'text', type: 'Text', fk: 'None', sample: 'Verification latency resolved.' }
        ]
      },
      mappings: [
        { source: 'id', target: 'ticket_id', confidence: '99%', sample: 'GLPI-1049' },
        { source: 'name', target: 'title', confidence: '98%', sample: 'Auth0 JWT verification latency' },
        { source: 'urgency', target: 'priority', confidence: '96%', sample: '4 -> P2' }
      ],
      previewRecords: [
        { id: 'GLPI-1049', priority: 'P2', title: 'Auth0 JWT verification latency > 850ms', ci: 'CI-AUTH-004', team: 'Security-SecOps' },
        { id: 'GLPI-1050', priority: 'P3', title: 'Kafka event bus consumer lag', ci: 'CI-KAFKA-007', team: 'Payment-Platform' },
        { id: 'GLPI-1051', priority: 'P4', title: 'Cloudflare HTTP/3 fallback variance', ci: 'CI-CDN-008', team: 'SRE-Core' }
      ]
    },

    otrs: {
      name: 'OTRS / Znuny',
      source: 'OTRS / Znuny Postmaster & Ticket SQL/JSON',
      entity: 'ticket, article & configitem Tables',
      qualityScore: '96/100',
      mappedCount: '9 / 9 (100%)',
      recordCount: '32 Tickets • 8 CIs',
      strategy: 'Extracted OTRS ticket numbers (tn), queue assignment groups, and ITSM configitem links into OpenNow.',
      tables: {
        tasks: [
          { source: 'tn', target: 'id (PK)', type: 'String', fk: 'Primary Key', sample: '202610110001' },
          { source: 'title', target: 'title', type: 'String', fk: 'None', sample: 'Payment Gateway webhook failure' },
          { source: 'priority_id', target: 'priority', type: 'Integer', fk: 'Normalized', sample: '5 -> P1, 4 -> P2' },
          { source: 'configitem_id', target: 'ci', type: 'Reference', fk: 'FK -> configitem', sample: 'CI-PAY-003' },
          { source: 'queue_id', target: 'team', type: 'Reference', fk: 'FK -> queue', sample: 'Payment-Platform' }
        ],
        users: [
          { source: 'id', target: 'user_id', type: 'Integer', fk: 'Primary Key', sample: '102' },
          { source: 'login', target: 'username', type: 'String', fk: 'None', sample: 'otrs-agent' },
          { source: 'email', target: 'email', type: 'Email', fk: 'None', sample: 'otrs-agent@company.de' }
        ],
        groups: [
          { source: 'id', target: 'team_id', type: 'Integer', fk: 'Primary Key', sample: '4' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Payment-Platform' }
        ],
        cmdb: [
          { source: 'id', target: 'ci_id', type: 'Integer', fk: 'Primary Key', sample: '290' },
          { source: 'name', target: 'name', type: 'String', fk: 'None', sample: 'Payment Gateway Service' }
        ],
        relations: [
          { source: 'source_key', target: 'source_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-INGRESS-005' },
          { source: 'target_key', target: 'target_ci_id', type: 'Reference', fk: 'FK -> CI', sample: 'CI-PAY-003' }
        ],
        journal: [
          { source: 'article.body', target: 'text', type: 'Text', fk: 'None', sample: '3DS confirmation completed.' }
        ]
      },
      mappings: [
        { source: 'tn', target: 'ticket_id', confidence: '99%', sample: 'OTRS-202610110001' },
        { source: 'title', target: 'title', confidence: '98%', sample: 'Payment Gateway webhook failure' },
        { source: 'priority_id', target: 'priority', confidence: '97%', sample: '5 -> P1' }
      ],
      previewRecords: [
        { id: 'OTRS-1001', priority: 'P1', title: 'Payment Gateway webhook failure on checkout', ci: 'CI-PAY-003', team: 'Payment-Platform' },
        { id: 'OTRS-1002', priority: 'P2', title: 'Redis session cache keyspace saturation', ci: 'CI-CACHE-002', team: 'Database-Ops' },
        { id: 'OTRS-1003', priority: 'P3', title: 'Kafka partition rebalancing delay', ci: 'CI-KAFKA-007', team: 'Payment-Platform' }
      ]
    }
  };

  // =========================================================================
  // DOM REFERENCES CACHE
  // =========================================================================

  const DOM = {};

  function cacheDom() {
    DOM.sidebar = document.getElementById('global-sidebar');
    DOM.btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
    DOM.btnMobileSidebarToggle = document.getElementById('btn-mobile-sidebar-toggle');
    DOM.btnSidebarZenToggle = document.getElementById('btn-sidebar-zen-toggle');
    DOM.btnZenModeToggle = document.getElementById('btn-zen-mode-toggle');
    DOM.btnZenExit = document.getElementById('btn-zen-exit');
    DOM.zenFloatingRestore = document.getElementById('zen-floating-restore');
    DOM.zenModeBadge = document.getElementById('zen-mode-badge');
    DOM.sidebarZenDot = document.getElementById('sidebar-zen-dot');
    DOM.breadcrumbView = document.getElementById('header-breadcrumb-view');

    DOM.navItems = document.querySelectorAll('.nav-item');
    DOM.viewPanels = document.querySelectorAll('.view-panel');
    DOM.brandHomeBtn = document.getElementById('brand-home-btn');

    // Header stats
    DOM.statActiveIncidents = document.getElementById('stat-active-incidents');
    DOM.statP1Count = document.getElementById('stat-p1-count');
    DOM.statCmdbHealth = document.getElementById('stat-cmdb-health');
    DOM.statSlaRate = document.getElementById('stat-sla-rate');
    DOM.sidebarActiveTicketsBadge = document.getElementById('sidebar-active-tickets-badge');
    DOM.slaUrgentText = document.getElementById('sla-urgent-text');

    // Incident Command
    DOM.ticketFilterSearch = document.getElementById('ticket-filter-search');
    DOM.ticketSearchClear = document.getElementById('ticket-search-clear');
    DOM.priorityFilterChips = document.querySelectorAll('[data-filter-priority]');
    DOM.teamFilterSelect = document.getElementById('team-filter-select');
    DOM.viewModeKanban = document.getElementById('view-mode-kanban');
    DOM.viewModeTable = document.getElementById('view-mode-table');
    DOM.kanbanContainer = document.getElementById('kanban-container');
    DOM.tableContainer = document.getElementById('table-container');
    DOM.incidentsTableBody = document.getElementById('incidents-table-body');

    // Kanban Columns
    DOM.cardsNew = document.getElementById('cards-NEW');
    DOM.cardsInProgress = document.getElementById('cards-IN_PROGRESS');
    DOM.cardsOnHold = document.getElementById('cards-ON_HOLD');
    DOM.cardsResolved = document.getElementById('cards-RESOLVED');
    DOM.colCountNew = document.getElementById('col-count-NEW');
    DOM.colCountInProgress = document.getElementById('col-count-IN_PROGRESS');
    DOM.colCountOnHold = document.getElementById('col-count-ON_HOLD');
    DOM.colCountResolved = document.getElementById('col-count-RESOLVED');

    // CMDB Elements
    DOM.cmdbSvgCanvas = document.getElementById('cmdb-svg-canvas');
    DOM.cmdbViewportLayer = document.getElementById('cmdb-viewport-layer');
    DOM.cmdbEdgesGroup = document.getElementById('cmdb-edges-group');
    DOM.cmdbNodesGroup = document.getElementById('cmdb-nodes-group');
    DOM.cmdbInspectorPanel = document.getElementById('cmdb-inspector-panel');
    DOM.btnCloseInspector = document.getElementById('btn-close-inspector');
    DOM.btnBlastSimulate = document.getElementById('btn-blast-simulate');
    DOM.cmdbTierFilterChips = document.querySelectorAll('[data-cmdb-tier]');
    DOM.btnGraphZoomIn = document.getElementById('btn-graph-zoom-in');
    DOM.btnGraphZoomOut = document.getElementById('btn-graph-zoom-out');
    DOM.btnGraphReset = document.getElementById('btn-graph-reset');

    // Inspector fields
    DOM.inspectorCiName = document.getElementById('inspector-ci-name');
    DOM.inspectorCiType = document.getElementById('inspector-ci-type');
    DOM.inspectorStatusText = document.getElementById('inspector-status-text');
    DOM.inspectorUptimeText = document.getElementById('inspector-uptime-text');
    DOM.inspectorMetricCpu = document.getElementById('inspector-metric-cpu');
    DOM.inspectorBarCpu = document.getElementById('inspector-bar-cpu');
    DOM.inspectorMetricMem = document.getElementById('inspector-metric-mem');
    DOM.inspectorBarMem = document.getElementById('inspector-bar-mem');
    DOM.inspectorMetricLatency = document.getElementById('inspector-metric-latency');
    DOM.inspectorBarLatency = document.getElementById('inspector-bar-latency');
    DOM.inspectorMetricErrors = document.getElementById('inspector-metric-errors');
    DOM.inspectorBarErrors = document.getElementById('inspector-bar-errors');
    DOM.inspectorCiId = document.getElementById('inspector-ci-id');
    DOM.inspectorCiTeam = document.getElementById('inspector-ci-team');
    DOM.inspectorCiCloud = document.getElementById('inspector-ci-cloud');
    DOM.inspectorUpstreamCount = document.getElementById('inspector-upstream-count');
    DOM.inspectorUpstreamList = document.getElementById('inspector-upstream-list');
    DOM.inspectorDownstreamCount = document.getElementById('inspector-downstream-count');
    DOM.inspectorDownstreamList = document.getElementById('inspector-downstream-list');
    DOM.inspectorActiveIncidents = document.getElementById('inspector-active-incidents');
    DOM.inspectorCreateTicketBtn = document.getElementById('inspector-create-ticket-btn');

    // Migration Studio Elements
    DOM.migrationResultContainer = document.getElementById('migration-analysis-result');
    DOM.migSourceTitle = document.getElementById('mig-source-title');
    DOM.migEntityType = document.getElementById('mig-entity-type');
    DOM.migQualityScore = document.getElementById('mig-quality-score');
    DOM.migMappedCount = document.getElementById('mig-mapped-count');
    DOM.migRecordCount = document.getElementById('mig-record-count');
    DOM.migStrategyNotice = document.getElementById('mig-ai-strategy-notice');
    DOM.migMappingTbody = document.getElementById('mig-mapping-tbody');
    DOM.migPreviewCardsContainer = document.getElementById('mig-preview-cards-container');
    DOM.schemaTabsContainer = document.getElementById('schema-tabs-container');
    DOM.schemaTabContent = document.getElementById('schema-tab-content');
    DOM.btnExecuteMigration = document.getElementById('btn-execute-migration');
    DOM.btnCancelMigration = document.getElementById('btn-cancel-migration');
    DOM.btnViewIngestedTickets = document.getElementById('btn-view-ingested-tickets');
    DOM.migProgressWrap = document.getElementById('mig-progress-wrap');
    DOM.migProgressFill = document.getElementById('mig-progress-fill');
    DOM.migProgressPct = document.getElementById('mig-progress-pct');
    DOM.migProgressLabel = document.getElementById('mig-progress-label');
    DOM.dropzone = document.getElementById('migration-file-dropzone');
    DOM.fileInput = document.getElementById('migration-file-input');
    DOM.btnBrowseFile = document.getElementById('btn-browse-file');

    // Slide-over Drawer
    DOM.ticketSlideover = document.getElementById('ticket-slideover');
    DOM.drawerBackdrop = document.getElementById('drawer-backdrop');
    DOM.drawerContentContainer = document.getElementById('drawer-content-container');

    // Create Modal & Cascading Selectors
    DOM.createModalBackdrop = document.getElementById('create-modal-backdrop');
    DOM.btnCreateIncidentTrigger = document.getElementById('btn-create-incident-trigger');
    DOM.btnCloseCreateModal = document.getElementById('btn-close-create-modal');
    DOM.btnCancelCreate = document.getElementById('btn-cancel-create');
    DOM.formCreateTicket = document.getElementById('form-create-ticket');
    DOM.inputTicketTitle = document.getElementById('input-ticket-title');
    DOM.inputTicketDesc = document.getElementById('input-ticket-desc');
    DOM.selectTicketCi = document.getElementById('select-ticket-ci');
    DOM.selectTicketPriority = document.getElementById('select-ticket-priority');
    DOM.selectTicketTeam = document.getElementById('select-ticket-team');
    DOM.selectTicketCategory = document.getElementById('select-ticket-category');
    DOM.selectTicketSubcategory = document.getElementById('select-ticket-subcategory');
    DOM.selectTicketItem = document.getElementById('select-ticket-item');
    DOM.selectTicketImpact = document.getElementById('select-ticket-impact');
    DOM.selectTicketUrgency = document.getElementById('select-ticket-urgency');
    DOM.createPriorityPreviewBadge = document.getElementById('create-priority-preview-badge');
    DOM.createPriorityCalcLabel = document.getElementById('create-priority-calc-label');
    DOM.aiTypingStatus = document.getElementById('ai-typing-status');
    DOM.liveAiCopilotContent = document.getElementById('live-ai-copilot-content');

    // Resolution Modal
    DOM.resolutionModalBackdrop = document.getElementById('resolution-modal-backdrop');
    DOM.btnCloseResolutionModal = document.getElementById('btn-close-resolution-modal');
    DOM.btnCancelResolution = document.getElementById('btn-cancel-resolution');
    DOM.formResolveTicket = document.getElementById('form-resolve-ticket');
    DOM.resolveTicketId = document.getElementById('resolve-ticket-id');
    DOM.selectResolutionCode = document.getElementById('select-resolution-code');
    DOM.inputRootCause = document.getElementById('input-root-cause');
    DOM.inputPreventiveAction = document.getElementById('input-preventive-action');
    DOM.checkFcr = document.getElementById('check-fcr');
    DOM.resModalTitle = document.getElementById('res-modal-title');

    // Hold Reason Modal
    DOM.holdModalBackdrop = document.getElementById('hold-modal-backdrop');
    DOM.btnCloseHoldModal = document.getElementById('btn-close-hold-modal');
    DOM.btnCancelHold = document.getElementById('btn-cancel-hold');
    DOM.formHoldTicket = document.getElementById('form-hold-ticket');
    DOM.holdTicketId = document.getElementById('hold-ticket-id');
    DOM.selectHoldReason = document.getElementById('select-hold-reason');
    DOM.inputHoldNotes = document.getElementById('input-hold-notes');
    DOM.holdModalTitle = document.getElementById('hold-modal-title');

    // Command Palette
    DOM.cmdPaletteModal = document.getElementById('cmd-palette-modal');
    DOM.cmdPaletteBtn = document.getElementById('cmd-palette-btn');
    DOM.cmdPaletteInput = document.getElementById('cmd-palette-input');
    DOM.cmdResultsContainer = document.getElementById('cmd-results-container');

    // AI Events
    DOM.aiEventsStreamList = document.getElementById('ai-events-stream-list');
    DOM.btnChaosSimulate = document.getElementById('btn-chaos-simulate');
    DOM.toastsContainer = document.getElementById('toasts-container');
  }

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  function initApp() {
    cacheDom();
    fetchCompanyDna().then(() => {
      updateHeaderIndustryPill();
      if (state.activeSetupModule === 'dna') {
        renderSetupCenter('dna');
      }
    });
    initSetupCenter();
    renderTickets();
    renderProblemManagement();
    renderChangeManagement();
    renderKnowledgeBase();
    renderOmnichannelHub();
    setupCmdbGraph();
    renderAiEvents();
    bindEvents();
    startSlaTicker();
    showToast('OpenNow Zen Enterprise Platform initialized on #fafafa canvas.', 'success');
  }

  // =========================================================================
  // GLOBAL METRICS & STATS
  // =========================================================================

  function renderGlobalStats() {
    const active = state.incidents.filter(i => i.status !== 'RESOLVED');
    const p1 = state.incidents.filter(i => i.priority === 'P1' && i.status !== 'RESOLVED');
    const criticalNodes = state.cmdbNodes.filter(n => n.health === 'critical').length;
    const totalNodes = state.cmdbNodes.length;
    const healthPct = (((totalNodes - criticalNodes) / totalNodes) * 100).toFixed(1);

    state.stats.activeIncidents = active.length;
    state.stats.p1Count = p1.length;
    state.stats.cmdbHealth = healthPct;

    if (DOM.statActiveIncidents) DOM.statActiveIncidents.textContent = active.length;
    if (DOM.statP1Count) DOM.statP1Count.textContent = p1.length;
    if (DOM.statCmdbHealth) DOM.statCmdbHealth.textContent = `${healthPct}%`;
    if (DOM.statSlaRate) DOM.statSlaRate.textContent = `${state.stats.slaRate}%`;
    if (DOM.sidebarActiveTicketsBadge) DOM.sidebarActiveTicketsBadge.textContent = active.length;

    const nearBreach = active.filter(i => i.slaSecondsRemaining > 0 && i.slaSecondsRemaining < 1800);
    if (DOM.slaUrgentText) {
      if (nearBreach.length > 0) {
        DOM.slaUrgentText.textContent = `${nearBreach.length} Incident${nearBreach.length > 1 ? 's' : ''} Near SLA Breach (<30m)`;
      } else {
        DOM.slaUrgentText.textContent = `All Active SLAs in Compliance`;
      }
    }
  }

  // =========================================================================
  // ZEN FOCUS MODE TOGGLE
  // =========================================================================

  function toggleZenMode() {
    state.zenMode = !state.zenMode;
    document.body.classList.toggle('zen-focus-mode', state.zenMode);

    if (DOM.btnZenModeToggle) DOM.btnZenModeToggle.classList.toggle('active', state.zenMode);
    if (DOM.btnSidebarZenToggle) DOM.btnSidebarZenToggle.classList.toggle('active', state.zenMode);

    if (state.zenMode) {
      showToast('☯ Zen Focus Mode Enabled: Peripheral chrome collapsed for tranquil focus.', 'ai');
    } else {
      showToast('Standard Mode Restored.', 'info');
    }
  }

  function toggleSidebarCollapse() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    DOM.sidebar.classList.toggle('collapsed', state.sidebarCollapsed);
  }

  // =========================================================================
  // VIEW 1: TICKETS / INCIDENT COMMAND (KANBAN & TABLE)
  // =========================================================================

  function getFilteredIncidents() {
    return state.incidents.filter(inc => {
      if (state.priorityFilter !== 'ALL' && inc.priority !== state.priorityFilter) {
        return false;
      }
      if (state.teamFilter !== 'ALL' && inc.team !== state.teamFilter) {
        return false;
      }
      if (state.searchQuery.trim() !== '') {
        const q = state.searchQuery.toLowerCase();
        const matchId = inc.id.toLowerCase().includes(q);
        const matchTitle = inc.title.toLowerCase().includes(q);
        const matchCi = inc.ciName.toLowerCase().includes(q);
        const matchTeam = inc.team.toLowerCase().includes(q);
        const matchDesc = inc.description.toLowerCase().includes(q);
        if (!matchId && !matchTitle && !matchCi && !matchTeam && !matchDesc) {
          return false;
        }
      }
      return true;
    });
  }

  function formatSlaTime(seconds) {
    if (seconds <= 0) return 'BREACHED';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs}h ${mins}m left`;
    }
    return `${mins}m ${secs}s left`;
  }

  function formatStatusLabel(st) {
    switch (st) {
      case 'NEW': return 'New / Triaging';
      case 'IN_PROGRESS': return 'In Progress';
      case 'ON_HOLD': return 'On Hold / Paused';
      case 'RESOLVED': return 'Resolved';
      case 'CLOSED': return 'Closed / Archived';
      default: return st;
    }
  }


  // =========================================================================
  // UNIFIED ENTERPRISE KANBAN OPERATIONS DASHBOARD (ALL OPEN WORK ITEMS)
  // =========================================================================

  function renderUnifiedKanbanBoard() {
    // 1. Aggregate All Open Work Items Across 4 ITIL Streams
    const allWorkItems = [];

    // Stream A: Incidents
    state.incidents.forEach(inc => {
      allWorkItems.push({
        id: inc.id,
        type: 'INCIDENT',
        typeLabel: '🚨 INCIDENT',
        typeClass: 'type-badge-incident',
        title: inc.title,
        priority: inc.priority,
        status: inc.status,
        metaLine: `${inc.ciName || inc.ci} • ${inc.team}`,
        slaTime: inc.slaSecondsRemaining,
        slaText: (inc.status === 'ON_HOLD' || inc.isPaused) ? `⏸ Paused (${escapeHtml(inc.holdReason || 'Hold')})` : inc.status === 'RESOLVED' ? '✓ Met SLA' : `⏱ ${formatSlaTime(inc.slaSecondsRemaining)}`,
        assignee: inc.team || 'SRE',
        raw: inc
      });
    });

    // Stream B: Problems
    state.problems.forEach(p => {
      allWorkItems.push({
        id: p.id,
        type: 'PROBLEM',
        typeLabel: '🔍 PROBLEM',
        typeClass: 'type-badge-problem',
        title: p.title,
        priority: 'P2',
        status: p.status === 'Resolved' ? 'RESOLVED' : p.isKedb ? 'ON_HOLD' : 'IN_PROGRESS',
        metaLine: `${p.ciName} • ${p.category}`,
        slaTime: 7200,
        slaText: p.isKedb ? '★ KEDB Published' : 'Investigating',
        assignee: 'Problem Ops',
        raw: p
      });
    });

    // Stream C: Changes
    state.changes.forEach(chg => {
      const isApproved = chg.cabStatus.includes('Approved');
      allWorkItems.push({
        id: chg.id,
        type: 'CHANGE',
        typeLabel: '🔄 CHANGE',
        typeClass: 'type-badge-change',
        title: chg.title,
        priority: chg.type === 'Emergency' ? 'P1' : 'P2',
        status: isApproved ? 'IN_PROGRESS' : 'NEW',
        metaLine: `${chg.ciName} • ${chg.type} Change`,
        slaTime: 14400,
        slaText: chg.scheduled,
        assignee: chg.lead,
        raw: chg
      });
    });

    // Stream D: Service Requests
    (state.serviceRequests || []).forEach(req => {
      allWorkItems.push({
        id: req.id,
        type: 'REQUEST',
        typeLabel: '📦 SERVICE REQ',
        typeClass: 'type-badge-request',
        title: req.title,
        priority: req.priority,
        status: req.status,
        metaLine: `${req.catalogItem} • ${req.requesterName}`,
        slaTime: req.slaHoursRemaining * 3600,
        slaText: req.slaDue,
        assignee: req.assignedTeam,
        raw: req
      });
    });

    // Update Counts in Toolbar
    const countAllEl = document.getElementById('count-kanban-all');
    if (countAllEl) countAllEl.textContent = allWorkItems.length;
    const countIncEl = document.getElementById('count-kanban-inc');
    if (countIncEl) countIncEl.textContent = state.incidents.length;
    const countPrbEl = document.getElementById('count-kanban-prb');
    if (countPrbEl) countPrbEl.textContent = state.problems.length;
    const countChgEl = document.getElementById('count-kanban-chg');
    if (countChgEl) countChgEl.textContent = state.changes.length;
    const countReqEl = document.getElementById('count-kanban-req');
    if (countReqEl) countReqEl.textContent = (state.serviceRequests || []).length;

    // Apply Filter Type
    let filtered = allWorkItems;
    if (state.kanbanTypeFilter && state.kanbanTypeFilter !== 'ALL') {
      filtered = filtered.filter(i => i.type === state.kanbanTypeFilter);
    }

    // Apply Priority Filter
    if (state.kanbanPriorityFilter && state.kanbanPriorityFilter !== 'ALL') {
      filtered = filtered.filter(i => i.priority === state.kanbanPriorityFilter);
    }

    // Apply Search Filter
    const searchVal = (document.getElementById('kanban-filter-search')?.value || '').toLowerCase().trim();
    if (searchVal) {
      filtered = filtered.filter(i => 
        i.title.toLowerCase().includes(searchVal) || 
        i.id.toLowerCase().includes(searchVal) || 
        i.metaLine.toLowerCase().includes(searchVal) ||
        i.assignee.toLowerCase().includes(searchVal)
      );
    }

    // Distribute into 4 Kanban Columns
    const cols = {
      NEW: [],
      IN_PROGRESS: [],
      ON_HOLD: [],
      RESOLVED: []
    };

    filtered.forEach(item => {
      if (cols[item.status]) {
        cols[item.status].push(item);
      } else {
        cols.NEW.push(item);
      }
    });

    const renderCard = (item) => {
      const pClass = (item.priority || 'P3').toLowerCase();
      return `
        <div class="ticket-card card-${pClass}" data-item-type="${item.type}" data-item-id="${item.id}" style="cursor:pointer;">
          <div class="kanban-item-headline">
            <span class="kanban-type-badge ${item.typeClass}">${item.typeLabel}</span>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="ticket-key font-mono" style="font-size:12px;">${item.id}</span>
              <span class="priority-pill pill-${pClass}">${item.priority}</span>
            </div>
          </div>
          <div class="ticket-title" style="font-size:13px; font-weight:700; margin-bottom:6px;">${escapeHtml(item.title)}</div>
          <div class="ticket-meta-tags" style="margin-bottom:8px;">
            <span class="ci-pill">${escapeHtml(item.metaLine)}</span>
          </div>
          <div class="ticket-card-footer">
            <span class="sla-timer-tag ${item.status === 'ON_HOLD' ? 'sla-paused' : 'sla-safe'}">${item.slaText}</span>
            <span class="team-pill" style="font-size:11px;">${escapeHtml(item.assignee)}</span>
          </div>
        </div>
      `;
    };

    if (DOM.cardsNew) DOM.cardsNew.innerHTML = cols.NEW.map(renderCard).join('');
    if (DOM.cardsInProgress) DOM.cardsInProgress.innerHTML = cols.IN_PROGRESS.map(renderCard).join('');
    if (DOM.cardsOnHold) DOM.cardsOnHold.innerHTML = cols.ON_HOLD.map(renderCard).join('');
    if (DOM.cardsResolved) DOM.cardsResolved.innerHTML = cols.RESOLVED.map(renderCard).join('');

    if (DOM.colCountNew) DOM.colCountNew.textContent = cols.NEW.length;
    if (DOM.colCountInProgress) DOM.colCountInProgress.textContent = cols.IN_PROGRESS.length;
    if (DOM.colCountOnHold) DOM.colCountOnHold.textContent = cols.ON_HOLD.length;
    if (DOM.colCountResolved) DOM.colCountResolved.textContent = cols.RESOLVED.length;

    // Bind card click triggers across all work item types
    document.querySelectorAll('#kanban-container .ticket-card').forEach(card => {
      card.addEventListener('click', () => {
        const itemType = card.getAttribute('data-item-type');
        const itemId = card.getAttribute('data-item-id');

        if (itemType === 'INCIDENT') {
          openTicketDrawer(itemId);
        } else if (itemType === 'PROBLEM') {
          open5WhysModal(itemId);
        } else if (itemType === 'CHANGE') {
          switchView('change-management');
          showToast(`Inspecting change request ${itemId}.`, 'info');
        } else if (itemType === 'REQUEST') {
          openServiceRequestDrawer(itemId);
        }
      });
    });
  }

  // =========================================================================
  // SERVICE REQUESTS QUEUE & FULFILLMENT MANAGEMENT
  // =========================================================================

  function renderServiceRequests() {
    const tbody = document.getElementById('requests-table-body');
    if (!tbody) return;

    let requests = state.serviceRequests || [];
    
    // Update KPI Header Metrics
    const statActive = document.getElementById('stat-requests-active');
    if (statActive) statActive.textContent = `${requests.filter(r => r.status !== 'RESOLVED').length} Active`;
    const statAppr = document.getElementById('stat-requests-approval');
    if (statAppr) statAppr.textContent = `${requests.filter(r => r.status === 'NEW').length} Pending`;
    const statFulfill = document.getElementById('stat-requests-fulfillment');
    if (statFulfill) statFulfill.textContent = `${requests.filter(r => r.status === 'IN_PROGRESS').length} In Progress`;

    // Filter Stage
    if (state.requestsStageFilter && state.requestsStageFilter !== 'ALL') {
      if (state.requestsStageFilter === 'Pending Approval') {
        requests = requests.filter(r => r.status === 'NEW');
      } else if (state.requestsStageFilter === 'In Fulfillment') {
        requests = requests.filter(r => r.status === 'IN_PROGRESS');
      } else if (state.requestsStageFilter === 'Fulfilled') {
        requests = requests.filter(r => r.status === 'RESOLVED');
      }
    }

    // Filter Search
    const search = (document.getElementById('requests-filter-search')?.value || '').toLowerCase().trim();
    if (search) {
      requests = requests.filter(r => 
        r.id.toLowerCase().includes(search) || 
        r.title.toLowerCase().includes(search) || 
        r.requesterName.toLowerCase().includes(search) || 
        r.catalogItem.toLowerCase().includes(search) ||
        r.department.toLowerCase().includes(search)
      );
    }

    tbody.innerHTML = requests.map(req => {
      let stageBadge = `<span class="badge-req-progress">⚡ ${escapeHtml(req.stage)}</span>`;
      if (req.status === 'NEW') {
        stageBadge = `<span class="badge-req-pending">⏸️ ${escapeHtml(req.stage)}</span>`;
      } else if (req.status === 'RESOLVED') {
        stageBadge = `<span class="badge-req-fulfilled">✓ ${escapeHtml(req.stage)}</span>`;
      }

      const pClass = req.priority.toLowerCase();

      return `
        <tr data-req-id="${req.id}" style="cursor:pointer;">
          <td class="font-mono text-emerald font-bold">${req.id}</td>
          <td>
            <div style="font-weight:700; color:var(--text-zen-primary); font-size:13px;">${escapeHtml(req.title)}</div>
            <div class="text-xs text-muted" style="margin-top:2px;">Offering: <strong>${escapeHtml(req.catalogItem)}</strong></div>
          </td>
          <td>
            <div style="font-weight:600; font-size:12.5px;">${escapeHtml(req.requesterName)}</div>
            <div class="text-xs text-muted">${escapeHtml(req.department)}</div>
          </td>
          <td>
            <span class="badge-tag ${req.approvalStatus.includes('Approved') ? 'text-emerald' : 'text-amber'}">${escapeHtml(req.approvalStatus)}</span>
          </td>
          <td>${stageBadge}</td>
          <td>
            <span class="priority-pill pill-${pClass}">${req.priority}</span>
          </td>
          <td class="font-mono text-xs ${req.status === 'RESOLVED' ? 'text-emerald font-semibold' : 'text-indigo'}">${escapeHtml(req.slaDue)}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:6px;">
              ${req.status === 'NEW' ? `
                <button class="btn btn-xs btn-zen-primary btn-req-approve" data-req-id="${req.id}" title="Approve service request">Approve</button>
              ` : req.status === 'IN_PROGRESS' ? `
                <button class="btn btn-xs btn-emerald-primary btn-req-fulfill" data-req-id="${req.id}" title="Complete procurement and mark delivered">Fulfill</button>
              ` : `
                <span class="text-emerald font-bold text-xs">✓ Delivered</span>
              `}
              <button class="btn btn-icon-sm btn-inspect-req" data-req-id="${req.id}" title="Inspect full request specifications">➔</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Row click
    tbody.querySelectorAll('tr').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        const id = row.getAttribute('data-req-id');
        openServiceRequestDrawer(id);
      });
    });

    tbody.querySelectorAll('.btn-inspect-req').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        openServiceRequestDrawer(id);
      });
    });

    tbody.querySelectorAll('.btn-req-approve').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        const req = (state.serviceRequests || []).find(r => r.id === id);
        if (req) {
          req.status = 'IN_PROGRESS';
          req.approvalStatus = 'Approved by Manager';
          req.stage = 'In Fulfillment / Asset Allocation';
          renderServiceRequests();
          if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
          showToast(`Service Request ${id} approved and routed for fulfillment!`, 'success');
        }
      });
    });

    tbody.querySelectorAll('.btn-req-fulfill').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-req-id');
        const req = (state.serviceRequests || []).find(r => r.id === id);
        if (req) {
          req.status = 'RESOLVED';
          req.stage = 'Fulfilled & Delivered';
          req.slaDue = '✓ Delivered within SLA';
          renderServiceRequests();
          if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
          showToast(`Service Request ${id} fulfilled and delivered to ${req.requesterName}!`, 'success');
        }
      });
    });
  }

  function openServiceRequestDrawer(reqId) {
    const req = (state.serviceRequests || []).find(r => r.id === reqId);
    if (!req) return;

    const modal = document.getElementById('request-detail-backdrop');
    const titleEl = document.getElementById('req-modal-title');
    const subEl = document.getElementById('req-modal-sub');
    const bodyEl = document.getElementById('req-modal-body');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `Service Request: ${req.id}`;
    if (subEl) subEl.textContent = `${req.catalogItem} • ${req.stage}`;

    bodyEl.innerHTML = `
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:14px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
          <h4 style="font-size:15px; font-weight:800; color:#0f172a;">${escapeHtml(req.title)}</h4>
          <span class="priority-pill pill-${req.priority.toLowerCase()}">${req.priority} Priority</span>
        </div>
        <div style="font-size:12.5px; color:#475569; line-height:1.5;">
          <strong>Business Justification:</strong> ${escapeHtml(req.justification)}
        </div>
      </div>

      <!-- Offering Specifications Table -->
      <div style="margin-bottom:14px;">
        <span style="font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; color:#64748b;">REQUESTED SPECIFICATIONS &amp; CONFIGURATION</span>
        <div class="req-specs-grid">
          ${Object.entries(req.specs || {}).map(([k, v]) => `
            <div class="req-spec-item">
              <span class="req-spec-label">${escapeHtml(k)}</span>
              <span class="req-spec-value">${escapeHtml(v)}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Requester & Approver Information -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:14px;">
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
          <span style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">REQUESTER DETAILS</span>
          <div style="display:flex; align-items:center; gap:10px; margin-top:8px;">
            <div class="tech-avatar-mini" style="background:#10b981; color:white;">${escapeHtml(req.requesterName.substring(0, 2).toUpperCase())}</div>
            <div>
              <strong style="font-size:13px; display:block;">${escapeHtml(req.requesterName)}</strong>
              <span class="text-xs text-muted">${escapeHtml(req.department)}</span>
            </div>
          </div>
        </div>

        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
          <span style="font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase;">FULFILLMENT STAGE</span>
          <div style="margin-top:8px;">
            <strong style="font-size:13px; color:#4f46e5; display:block;">${escapeHtml(req.stage)}</strong>
            <span class="text-xs text-muted">Assigned Queue: <strong>${escapeHtml(req.assignedTeam)}</strong></span>
          </div>
        </div>
      </div>

      <!-- Multi-tier Approver Chain Status -->
      <div class="req-approval-chain-box">
        <div class="req-approval-header">
          <span>✓</span>
          <span>MULTI-TIER ITIL APPROVAL CHAIN</span>
        </div>
        <p style="font-size:12px; color:#15803d;">
          Current Approval Status: <strong>${escapeHtml(req.approvalStatus)}</strong> (Designated Approver: ${escapeHtml(req.approver)})
        </p>
      </div>

      <!-- Action Footer -->
      <div style="display:flex; align-items:center; justify-content:space-between; margin-top:18px; padding-top:14px; border-top:1px solid #e2e8f0;">
        <span class="font-mono text-xs text-muted">Estimated Cost: <strong>$${req.cost.toFixed(2)}</strong></span>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-sm btn-zen-outline" id="btn-close-req-modal-action">Close</button>
          ${req.status === 'NEW' ? `
            <button class="btn btn-sm btn-zen-primary" id="btn-modal-req-approve">Approve Request</button>
          ` : req.status === 'IN_PROGRESS' ? `
            <button class="btn btn-sm btn-emerald-primary" id="btn-modal-req-fulfill">Mark Fulfilled &amp; Delivered</button>
          ` : `
            <span class="text-emerald font-bold text-xs" style="align-self:center;">✓ Request Delivered</span>
          `}
        </div>
      </div>
    `;

    modal.classList.add('open');

    document.getElementById('btn-close-req-modal-action')?.addEventListener('click', () => modal.classList.remove('open'));
    document.getElementById('btn-close-req-modal')?.addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });

    document.getElementById('btn-modal-req-approve')?.addEventListener('click', () => {
      req.status = 'IN_PROGRESS';
      req.approvalStatus = 'Approved by Manager';
      req.stage = 'In Fulfillment / Asset Allocation';
      modal.classList.remove('open');
      renderServiceRequests();
      if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
      showToast(`Request ${req.id} approved!`, 'success');
    });

    document.getElementById('btn-modal-req-fulfill')?.addEventListener('click', () => {
      req.status = 'RESOLVED';
      req.stage = 'Fulfilled & Delivered';
      req.slaDue = '✓ Delivered within SLA';
      modal.classList.remove('open');
      renderServiceRequests();
      if (state.activeView === 'kanban-board') renderUnifiedKanbanBoard();
      showToast(`Request ${req.id} fulfilled and delivered!`, 'success');
    });
  }

  function renderTickets() {
    const filtered = getFilteredIncidents();

    const cols = {
      NEW: [],
      IN_PROGRESS: [],
      ON_HOLD: [],
      RESOLVED: []
    };

    filtered.forEach(inc => {
      if (cols[inc.status]) {
        cols[inc.status].push(inc);
      }
    });

    if (DOM.cardsNew) DOM.cardsNew.innerHTML = cols.NEW.map(renderKanbanCardHtml).join('');
    if (DOM.cardsInProgress) DOM.cardsInProgress.innerHTML = cols.IN_PROGRESS.map(renderKanbanCardHtml).join('');
    if (DOM.cardsOnHold) DOM.cardsOnHold.innerHTML = cols.ON_HOLD.map(renderKanbanCardHtml).join('');
    if (DOM.cardsResolved) DOM.cardsResolved.innerHTML = cols.RESOLVED.map(renderKanbanCardHtml).join('');

    if (DOM.colCountNew) DOM.colCountNew.textContent = cols.NEW.length;
    if (DOM.colCountInProgress) DOM.colCountInProgress.textContent = cols.IN_PROGRESS.length;
    if (DOM.colCountOnHold) DOM.colCountOnHold.textContent = cols.ON_HOLD.length;
    if (DOM.colCountResolved) DOM.colCountResolved.textContent = cols.RESOLVED.length;

    attachKanbanEvents();

    if (DOM.incidentsTableBody) {
      DOM.incidentsTableBody.innerHTML = filtered.map(inc => {
        const isCriticalSla = inc.slaSecondsRemaining > 0 && inc.slaSecondsRemaining < 1800;
        const slaClass = (inc.status === 'ON_HOLD' || inc.isPaused) ? 'text-amber font-semibold' : inc.status === 'RESOLVED' ? 'text-emerald font-semibold' : inc.slaSecondsRemaining <= 0 ? 'text-rose font-bold' : isCriticalSla ? 'text-rose' : 'text-secondary';

        let slaColText = formatSlaTime(inc.slaSecondsRemaining);
        if (inc.status === 'ON_HOLD' || inc.isPaused) {
          slaColText = `⏸️ PAUSED (${formatDurationShort(inc.totalPausedSeconds || 0)})`;
        } else if (inc.status === 'RESOLVED') {
          slaColText = `✓ Met SLA`;
        }

        return `
          <tr data-ticket-id="${inc.id}">
            <td class="font-mono text-indigo font-semibold">${inc.id}</td>
            <td>
              <span class="priority-pill pill-${inc.priority.toLowerCase()}">
                ${inc.priority === 'P1' ? '<span class="critical-radar-dot"></span>' : ''}
                ${inc.priority}
              </span>
            </td>
            <td>
              <div class="table-ticket-title">${escapeHtml(inc.title)}</div>
              <div class="table-ticket-desc">${escapeHtml(inc.description)}</div>
            </td>
            <td><span class="ci-pill">${escapeHtml(inc.ciName)}</span></td>
            <td><span class="team-pill">${escapeHtml(inc.team)}</span></td>
            <td>
              <span class="badge-tag ${inc.status === 'ON_HOLD' ? 'text-amber' : inc.status === 'RESOLVED' ? 'text-emerald' : ''}">
                ${formatStatusLabel(inc.status)}${inc.status === 'ON_HOLD' && inc.holdReason ? ` • ${escapeHtml(inc.holdReason)}` : ''}
              </span>
            </td>
            <td class="font-mono ${slaClass}">${slaColText}</td>
            <td class="text-right">
              <button class="btn btn-icon-sm btn-inspect-row" data-ticket-id="${inc.id}" title="Inspect incident details">➔</button>
            </td>
          </tr>
        `;
      }).join('');

      DOM.incidentsTableBody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', () => {
          const id = row.getAttribute('data-ticket-id');
          openTicketDrawer(id);
        });
      });
    }

    renderGlobalStats();
  }

  function renderKanbanCardHtml(inc) {
    const isCriticalSla = inc.slaSecondsRemaining > 0 && inc.slaSecondsRemaining < 1800;
    const isBreached = inc.slaSecondsRemaining <= 0;
    const slaClass = (inc.status === 'ON_HOLD' || inc.isPaused) ? 'sla-paused' : isBreached ? 'sla-breach' : isCriticalSla ? 'sla-warn' : 'sla-safe';

    let slaTagText = `⏱ ${formatSlaTime(inc.slaSecondsRemaining)}`;
    if (inc.status === 'ON_HOLD' || inc.isPaused) {
      slaTagText = `⏸️ PAUSED (${escapeHtml(inc.holdReason || 'On Hold')})`;
    } else if (inc.status === 'RESOLVED') {
      slaTagText = `✓ Met SLA`;
    }

    return `
      <div class="ticket-card card-${inc.priority.toLowerCase()}" 
           id="ticket-${inc.id}" 
           data-ticket-id="${inc.id}" 
           draggable="true">
        <div class="ticket-card-header">
          <span class="ticket-key">${inc.id}</span>
          <span class="priority-pill pill-${inc.priority.toLowerCase()}">
            ${inc.priority === 'P1' ? '<span class="critical-radar-dot"></span>' : ''}
            ${inc.priority}
          </span>
        </div>
        <div class="ticket-title">${escapeHtml(inc.title)}</div>
        <div class="ticket-meta-tags">
          <span class="ci-pill" title="Affected Configuration Item">${escapeHtml(inc.ciName)}</span>
          <span class="team-pill" title="Assignment Team">${escapeHtml(inc.team)}</span>
        </div>
        <div class="ticket-card-footer">
          <span class="sla-timer-tag ${slaClass}" title="SLA Countdown: ${formatSlaTime(inc.slaSecondsRemaining)} • Paused for ${formatDurationShort(inc.totalPausedSeconds || 0)}">
            ${slaTagText}
          </span>
          <span class="ai-tag" title="AI Confidence">${inc.aiConfidence} AI</span>
        </div>
      </div>
    `;
  }

  function attachKanbanEvents() {
    const cards = document.querySelectorAll('.ticket-card');
    const dropzones = document.querySelectorAll('.dropzone');

    cards.forEach(card => {
      card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', card.getAttribute('data-ticket-id'));
        card.classList.add('dragging');
      });

      card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
      });

      card.addEventListener('click', () => {
        const id = card.getAttribute('data-ticket-id');
        openTicketDrawer(id);
      });
    });

    dropzones.forEach(zone => {
      zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
      });

      zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
      });

      zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const ticketId = e.dataTransfer.getData('text/plain');
        const targetColumn = zone.closest('.kanban-column');
        if (!targetColumn) return;
        const newStatus = targetColumn.getAttribute('data-status');

        const inc = state.incidents.find(i => i.id === ticketId);
        if (!inc) return;

        if (newStatus === 'ON_HOLD' && inc.status !== 'ON_HOLD') {
          openHoldModal(ticketId);
          return;
        }

        if (newStatus === 'RESOLVED' && inc.status !== 'RESOLVED') {
          openResolutionModal(ticketId);
          return;
        }

        if (inc.status !== newStatus) {
          inc.status = newStatus;
          inc.isPaused = false;
          inc.timeline.unshift({
            time: 'Just now',
            user: 'Alex Rivera (SRE)',
            text: `Moved incident to ${formatStatusLabel(newStatus)} on Kanban board.`
          });
          renderTickets();
          showToast(`${inc.id} moved to ${formatStatusLabel(newStatus)}`, 'info');
        }
      });
    });
  }

  function startSlaTicker() {
    setInterval(() => {
      let needsRerender = false;
      state.incidents.forEach(inc => {
        if (inc.status === 'ON_HOLD' || inc.isPaused) {
          inc.totalPausedSeconds = (inc.totalPausedSeconds || 0) + 1;
          needsRerender = true;
        } else if (inc.status !== 'RESOLVED' && inc.status !== 'CLOSED' && inc.slaSecondsRemaining > 0) {
          inc.slaSecondsRemaining -= 1;
          needsRerender = true;
        }
      });

      if (needsRerender) {
        document.querySelectorAll('.sla-timer-tag').forEach(el => {
          const card = el.closest('.ticket-card');
          if (card) {
            const id = card.getAttribute('data-ticket-id');
            const inc = state.incidents.find(i => i.id === id);
            if (inc) {
              if (inc.status === 'ON_HOLD' || inc.isPaused) {
                el.className = 'sla-timer-tag sla-paused';
                el.textContent = `⏸️ PAUSED (${inc.holdReason || 'On Hold'})`;
                el.title = `SLA Clock Paused (${formatSlaTime(inc.slaSecondsRemaining)} left) • Paused for ${formatDurationShort(inc.totalPausedSeconds || 0)}`;
              } else if (inc.status === 'RESOLVED') {
                el.className = 'sla-timer-tag sla-safe';
                el.textContent = `✓ Met SLA`;
              } else {
                const isCrit = inc.slaSecondsRemaining > 0 && inc.slaSecondsRemaining < 1800;
                const isBr = inc.slaSecondsRemaining <= 0;
                el.className = `sla-timer-tag ${isBr ? 'sla-breach' : isCrit ? 'sla-warn' : 'sla-safe'}`;
                el.textContent = `⏱ ${formatSlaTime(inc.slaSecondsRemaining)}`;
              }
            }
          }
        });

        // Update live SLA in open ticket drawer if open
        if (state.selectedTicket) {
          const openInc = state.selectedTicket;
          const liveBannerCountdown = document.getElementById('drawer-sla-countdown-live');
          const liveAccumulated = document.getElementById('drawer-sla-accumulated-live');
          if (liveBannerCountdown) {
            if (openInc.status === 'ON_HOLD' || openInc.isPaused) {
              liveBannerCountdown.textContent = `${formatSlaTime(openInc.slaSecondsRemaining)} remaining`;
            } else if (openInc.status === 'RESOLVED') {
              liveBannerCountdown.textContent = 'MET RESOLUTION TARGET';
            } else {
              liveBannerCountdown.textContent = formatSlaTime(openInc.slaSecondsRemaining);
            }
          }
          if (liveAccumulated) {
            liveAccumulated.textContent = `Paused: ${formatDurationShort(openInc.totalPausedSeconds || 0)}`;
          }
        }
      }
    }, 1000);
  }

  // =========================================================================
  // VIEW 2: INTERACTIVE CMDB TOPOLOGY GRAPH (LIGHT MODE)
  // =========================================================================

  function setupCmdbGraph() {
    renderCmdbEdges();
    renderCmdbNodes();
    bindGraphInteractions();
  }

  function renderCmdbEdges() {
    if (!DOM.cmdbEdgesGroup) return;

    let pathsHtml = '';
    state.cmdbNodes.forEach(source => {
      source.downstream.forEach(targetId => {
        const target = state.cmdbNodes.find(n => n.id === targetId);
        if (!target) return;

        const sx = source.x + 90;
        const sy = source.y + 37;
        const tx = target.x + 90;
        const ty = target.y + 37;

        const dx = tx - sx;
        const cx1 = sx + dx * 0.5;
        const cy1 = sy;
        const cx2 = sx + dx * 0.5;
        const cy2 = ty;

        const pathD = `M ${sx} ${sy} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${tx} ${ty}`;
        const edgeId = `edge-${source.id}-${target.id}`;

        pathsHtml += `
          <path id="${edgeId}" class="cmdb-edge-path" d="${pathD}" 
                data-source="${source.id}" data-target="${target.id}" 
                marker-end="url(#arrow-default)" />
        `;
      });
    });

    DOM.cmdbEdgesGroup.innerHTML = pathsHtml;
  }

  function renderCmdbNodes() {
    if (!DOM.cmdbNodesGroup) return;

    let nodesHtml = '';
    state.cmdbNodes.forEach(node => {
      const statusClass = `node-${node.health}`;
      const pingColor = node.health === 'critical' ? '#e11d48' : node.health === 'degraded' ? '#d97706' : '#059669';

      nodesHtml += `
        <g class="cmdb-node-group ${statusClass}" id="node-g-${node.id}" data-node-id="${node.id}" transform="translate(${node.x}, ${node.y})">
          <rect class="node-card-rect" width="180" height="74" rx="8" ry="8" />
          <circle cx="16" cy="20" r="4.5" fill="${pingColor}" />
          ${node.health === 'critical' ? `<circle cx="16" cy="20" r="8" fill="none" stroke="${pingColor}" stroke-width="1.5" opacity="0.6" />` : ''}

          <text class="node-header-text" x="28" y="24">${escapeXml(node.name)}</text>
          <text class="node-sub-text" x="28" y="38">${escapeXml(node.type)}</text>

          <line x1="12" y1="46" x2="168" y2="46" stroke="#e2e8f0" stroke-width="1" />
          <text class="node-metric-text" x="14" y="60">CPU: ${node.cpu}% • ${node.latency}ms</text>
          <text class="node-metric-text" x="105" y="60" fill="${node.health === 'critical' ? '#e11d48' : '#64748b'}">
            ${node.health === 'critical' ? '1 ACTIVE P1' : 'Operational'}
          </text>
        </g>
      `;
    });

    DOM.cmdbNodesGroup.innerHTML = nodesHtml;

    document.querySelectorAll('.cmdb-node-group').forEach(nodeEl => {
      nodeEl.addEventListener('click', () => {
        const nodeId = nodeEl.getAttribute('data-node-id');
        openCmdbInspector(nodeId);
      });
    });
  }

  function bindGraphInteractions() {
    let isPanning = false;
    let startX = 0, startY = 0;
    let currentX = 20, currentY = 20;
    let currentScale = 0.95;

    const canvas = DOM.cmdbSvgCanvas;
    const viewport = DOM.cmdbViewportLayer;

    function updateTransform() {
      if (viewport) {
        viewport.setAttribute('transform', `translate(${currentX}, ${currentY}) scale(${currentScale})`);
      }
    }
    updateTransform();

    if (canvas) {
      canvas.addEventListener('mousedown', (e) => {
        if (e.target.closest('.cmdb-node-group')) return;
        isPanning = true;
        startX = e.clientX - currentX;
        startY = e.clientY - currentY;
      });
    }

    window.addEventListener('mousemove', (e) => {
      if (!isPanning) return;
      currentX = e.clientX - startX;
      currentY = e.clientY - startY;
      updateTransform();
    });

    window.addEventListener('mouseup', () => {
      isPanning = false;
    });

    if (DOM.btnGraphZoomIn) {
      DOM.btnGraphZoomIn.addEventListener('click', () => {
        currentScale = Math.min(currentScale + 0.15, 2.0);
        updateTransform();
      });
    }
    if (DOM.btnGraphZoomOut) {
      DOM.btnGraphZoomOut.addEventListener('click', () => {
        currentScale = Math.max(currentScale - 0.15, 0.4);
        updateTransform();
      });
    }
    if (DOM.btnGraphReset) {
      DOM.btnGraphReset.addEventListener('click', () => {
        currentX = 20;
        currentY = 20;
        currentScale = 0.95;
        updateTransform();
        resetBlastSimulation();
      });
    }

    if (DOM.cmdbTierFilterChips) {
      DOM.cmdbTierFilterChips.forEach(chip => {
        chip.addEventListener('click', () => {
          DOM.cmdbTierFilterChips.forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          const tier = chip.getAttribute('data-cmdb-tier');

          document.querySelectorAll('.cmdb-node-group').forEach(nodeEl => {
            const id = nodeEl.getAttribute('data-node-id');
            const node = state.cmdbNodes.find(n => n.id === id);
            if (tier === 'ALL' || (node && node.tier === tier)) {
              nodeEl.style.opacity = '1';
              nodeEl.style.filter = 'none';
            } else {
              nodeEl.style.opacity = '0.2';
              nodeEl.style.filter = 'grayscale(1)';
            }
          });
        });
      });
    }

    if (DOM.btnBlastSimulate) {
      DOM.btnBlastSimulate.addEventListener('click', toggleBlastRadiusSimulation);
    }
    if (DOM.btnCloseInspector) {
      DOM.btnCloseInspector.addEventListener('click', () => {
        DOM.cmdbInspectorPanel.classList.remove('open');
      });
    }
  }

  function toggleBlastRadiusSimulation() {
    if (state.isBlastSimulating) {
      resetBlastSimulation();
      showToast('Blast radius simulation stopped.', 'info');
      return;
    }

    state.isBlastSimulating = true;
    DOM.btnBlastSimulate.innerHTML = '<span>Stop Simulation ◼</span>';
    DOM.btnBlastSimulate.classList.add('btn-zen-primary');

    const affectedNodeIds = new Set(['CI-PAY-003', 'CI-DB-001', 'CI-CACHE-002', 'CI-KAFKA-007']);

    document.querySelectorAll('.cmdb-edge-path').forEach(edge => {
      const source = edge.getAttribute('data-source');
      const target = edge.getAttribute('data-target');
      if (affectedNodeIds.has(source) && affectedNodeIds.has(target)) {
        edge.classList.add('edge-blast-radius');
        edge.setAttribute('marker-end', 'url(#arrow-blast)');
      }
    });

    affectedNodeIds.forEach(id => {
      const el = document.getElementById(`node-g-${id}`);
      if (el) {
        el.classList.add('node-critical');
        el.style.filter = 'url(#glow-rose)';
      }
    });

    showToast('🚨 Cascading Blast Radius Simulated: 4 Services impacted across Payment Mesh.', 'error');
    openCmdbInspector('CI-PAY-003');
  }

  function resetBlastSimulation() {
    state.isBlastSimulating = false;
    if (DOM.btnBlastSimulate) {
      DOM.btnBlastSimulate.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg><span>Simulate Blast Radius</span>';
      DOM.btnBlastSimulate.classList.remove('btn-zen-primary');
    }

    document.querySelectorAll('.cmdb-edge-path').forEach(edge => {
      edge.classList.remove('edge-blast-radius');
      edge.setAttribute('marker-end', 'url(#arrow-default)');
    });

    document.querySelectorAll('.cmdb-node-group').forEach(el => {
      el.style.filter = 'none';
      const id = el.getAttribute('data-node-id');
      const node = state.cmdbNodes.find(n => n.id === id);
      if (node && node.health !== 'critical') {
        el.classList.remove('node-critical');
      }
    });
  }

  function openCmdbInspector(nodeId) {
    const node = state.cmdbNodes.find(n => n.id === nodeId);
    if (!node) return;

    state.selectedNode = node;

    if (DOM.inspectorCiName) DOM.inspectorCiName.textContent = node.name;
    if (DOM.inspectorCiType) DOM.inspectorCiType.textContent = `${node.tier} Tier • ${node.type}`;
    if (DOM.inspectorCiId) DOM.inspectorCiId.textContent = node.id;
    if (DOM.inspectorCiTeam) DOM.inspectorCiTeam.textContent = node.team;
    if (DOM.inspectorCiCloud) DOM.inspectorCiCloud.textContent = node.provider;
    if (DOM.inspectorUptimeText) DOM.inspectorUptimeText.textContent = `Uptime: ${node.uptime}`;

    const isCritical = node.health === 'critical';
    if (DOM.inspectorStatusText) {
      DOM.inspectorStatusText.textContent = isCritical ? 'CRITICAL OUTAGE (Active P1)' : node.health === 'degraded' ? 'DEGRADED PERFORMANCE' : 'HEALTHY & OPERATIONAL';
    }

    if (DOM.inspectorMetricCpu) DOM.inspectorMetricCpu.textContent = `${node.cpu}%`;
    if (DOM.inspectorBarCpu) DOM.inspectorBarCpu.style.width = `${node.cpu}%`;

    if (DOM.inspectorMetricMem) DOM.inspectorMetricMem.textContent = `${node.mem}%`;
    if (DOM.inspectorBarMem) DOM.inspectorBarMem.style.width = `${node.mem}%`;

    if (DOM.inspectorMetricLatency) DOM.inspectorMetricLatency.textContent = `${node.latency}ms`;
    if (DOM.inspectorBarLatency) DOM.inspectorBarLatency.style.width = `${Math.min(node.latency / 15, 100)}%`;

    if (DOM.inspectorMetricErrors) DOM.inspectorMetricErrors.textContent = `${node.errors}%`;
    if (DOM.inspectorBarErrors) DOM.inspectorBarErrors.style.width = `${Math.min(node.errors * 4, 100)}%`;

    if (DOM.inspectorUpstreamCount) DOM.inspectorUpstreamCount.textContent = node.upstream.length;
    if (DOM.inspectorUpstreamList) {
      DOM.inspectorUpstreamList.innerHTML = node.upstream.length > 0
        ? node.upstream.map(id => `<span class="dep-chip" data-node-id="${id}">${id}</span>`).join('')
        : '<span class="text-muted text-sm">None (Edge Entrypoint)</span>';
    }

    if (DOM.inspectorDownstreamCount) DOM.inspectorDownstreamCount.textContent = node.downstream.length;
    if (DOM.inspectorDownstreamList) {
      DOM.inspectorDownstreamList.innerHTML = node.downstream.length > 0
        ? node.downstream.map(id => `<span class="dep-chip" data-node-id="${id}">${id}</span>`).join('')
        : '<span class="text-muted text-sm">None (Terminal Node)</span>';
    }

    const linkedIncidents = state.incidents.filter(i => i.ci === node.id && i.status !== 'RESOLVED');
    if (DOM.inspectorActiveIncidents) {
      DOM.inspectorActiveIncidents.innerHTML = linkedIncidents.length > 0
        ? linkedIncidents.map(inc => `
            <div class="ticket-card card-${inc.priority.toLowerCase()} mt-2" data-ticket-id="${inc.id}" style="cursor:pointer;">
              <div class="ticket-card-header">
                <span class="ticket-key">${inc.id}</span>
                <span class="priority-pill pill-${inc.priority.toLowerCase()}">${inc.priority}</span>
              </div>
              <div class="ticket-title" style="font-size:12px;">${escapeHtml(inc.title)}</div>
            </div>
          `).join('')
        : '<div class="text-muted text-sm" style="padding:6px 0;">No active incidents on this CI.</div>';

      DOM.inspectorActiveIncidents.querySelectorAll('.ticket-card').forEach(c => {
        c.addEventListener('click', () => {
          openTicketDrawer(c.getAttribute('data-ticket-id'));
        });
      });
    }

    if (DOM.inspectorCreateTicketBtn) {
      DOM.inspectorCreateTicketBtn.onclick = () => {
        openCreateModal({ ci: node.id, priority: isCritical ? 'P1' : 'P2' });
      };
    }

    document.querySelectorAll('.dep-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const targetId = chip.getAttribute('data-node-id');
        openCmdbInspector(targetId);
      });
    });

    DOM.cmdbInspectorPanel.classList.add('open');
  }

  // =========================================================================
  // VIEW 3: TOP 10 NATIVE MIGRATION HUB & RELATIONAL SCHEMA VISUALIZER
  // =========================================================================

  function handlePlatformSampleLoad(platformKey) {
    const platform = TOP_10_PLATFORMS[platformKey] || TOP_10_PLATFORMS.servicenow;
    state.currentPlatform = platformKey;

    if (DOM.migSourceTitle) DOM.migSourceTitle.textContent = `${platform.name}: ${platform.source}`;
    if (DOM.migEntityType) DOM.migEntityType.textContent = platform.entity;
    if (DOM.migQualityScore) DOM.migQualityScore.textContent = platform.qualityScore;
    if (DOM.migMappedCount) DOM.migMappedCount.textContent = platform.mappedCount;
    if (DOM.migRecordCount) DOM.migRecordCount.textContent = platform.recordCount;

    if (DOM.migStrategyNotice) {
      DOM.migStrategyNotice.innerHTML = `
        <span class="ai-star-sparkle">✦</span>
        <span><strong>AI Relational Synthesis Engine:</strong> ${escapeHtml(platform.strategy)}</span>
      `;
    }

    renderRelationalSchemaVisualizer(platformKey, state.activeSchemaTab);

    if (DOM.migMappingTbody) {
      DOM.migMappingTbody.innerHTML = platform.mappings.map(m => `
        <tr>
          <td><span class="mapping-source-badge">${escapeHtml(m.source)}</span></td>
          <td class="text-center font-bold text-muted">→</td>
          <td><span class="mapping-target-badge">${escapeHtml(m.target)}</span></td>
          <td><span class="confidence-pill">${m.confidence} Confidence</span></td>
          <td class="font-mono text-sm text-secondary">${escapeHtml(m.sample)}</td>
        </tr>
      `).join('');
    }

    if (DOM.migPreviewCardsContainer) {
      DOM.migPreviewCardsContainer.innerHTML = platform.previewRecords.map(r => `
        <div class="record-preview-box">
          <div class="record-header-row">
            <span class="font-mono text-indigo font-bold">${r.id}</span>
            <span class="priority-pill pill-${r.priority.toLowerCase()}">${r.priority}</span>
          </div>
          <div class="preview-title">${escapeHtml(r.title)}</div>
          <div class="ticket-meta-tags mt-2">
            <span class="ci-pill">${escapeHtml(r.ci)}</span>
            <span class="team-pill">${escapeHtml(r.team)}</span>
          </div>
        </div>
      `).join('');
    }

    if (DOM.migrationResultContainer) {
      DOM.migrationResultContainer.style.display = 'flex';
      DOM.migrationResultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    if (DOM.btnViewIngestedTickets) DOM.btnViewIngestedTickets.style.display = 'none';
    if (DOM.btnExecuteMigration) {
      DOM.btnExecuteMigration.style.display = 'inline-flex';
      DOM.btnExecuteMigration.disabled = false;
    }
    if (DOM.migProgressWrap) DOM.migProgressWrap.style.display = 'none';

    showToast(`Loaded authentic relational schema for ${platform.name}`, 'ai');
  }

  function renderRelationalSchemaVisualizer(platformKey, tabKey) {
    const platform = TOP_10_PLATFORMS[platformKey] || TOP_10_PLATFORMS.servicenow;
    const tableData = platform.tables[tabKey] || platform.tables.tasks;

    let html = `
      <div class="schema-table-view">
        <table class="zen-data-table">
          <thead>
            <tr>
              <th width="240">Legacy Source Column</th>
              <th width="30"></th>
              <th width="220">Target Property</th>
              <th width="140">Normalized Type</th>
              <th width="180">FK Relation Binding</th>
              <th>Sample Ingested Value</th>
            </tr>
          </thead>
          <tbody>
            ${tableData.map(row => `
              <tr>
                <td><span class="schema-source-pill">${escapeHtml(row.source)}</span></td>
                <td class="text-center font-bold text-muted">➔</td>
                <td><span class="schema-target-pill">${escapeHtml(row.target)}</span></td>
                <td><span class="badge-tag">${escapeHtml(row.type)}</span></td>
                <td><span class="schema-fk-pill">${escapeHtml(row.fk)}</span></td>
                <td class="font-mono text-sm text-secondary">${escapeHtml(row.sample)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    if (DOM.schemaTabContent) {
      DOM.schemaTabContent.innerHTML = html;
    }
  }

  function executeMigrationProcess() {
    const platform = TOP_10_PLATFORMS[state.currentPlatform] || TOP_10_PLATFORMS.servicenow;

    if (DOM.migProgressWrap) DOM.migProgressWrap.style.display = 'block';
    if (DOM.btnExecuteMigration) DOM.btnExecuteMigration.disabled = true;

    let progress = 0;
    const interval = setInterval(() => {
      progress += 14;
      if (DOM.migProgressFill) DOM.migProgressFill.style.width = `${Math.min(progress, 100)}%`;
      if (DOM.migProgressPct) DOM.migProgressPct.textContent = `${Math.min(progress, 100)}%`;

      if (progress >= 100) {
        clearInterval(interval);

        platform.previewRecords.forEach((rec, idx) => {
          const newId = `INC-${9300 + idx}`;
          state.incidents.unshift({
            id: newId,
            title: `[${platform.name}] ${rec.title}`,
            description: `Automated migration from ${platform.source}. Source key: ${rec.id}. Foreign keys resolved, journal work notes bound.`,
            ci: rec.ci,
            ciName: state.cmdbNodes.find(n => n.id === rec.ci)?.name || rec.ci,
            priority: rec.priority,
            status: 'NEW',
            team: rec.team,
            caller: 'migration-engine@opennow.io',
            createdAt: 'Just now',
            slaSecondsRemaining: 3600 * (rec.priority === 'P1' ? 1 : rec.priority === 'P2' ? 4 : 8),
            slaInitialSeconds: 14400,
            aiTriageDone: true,
            aiConfidence: '99.4%',
            timeline: [
              { time: 'Just now', user: 'AI Migration Hub', text: `Migrated record from ${platform.name}. Reconciled relational keys and bound to CMDB item.`, isAi: true }
            ]
          });
        });

        renderTickets();

        if (DOM.migProgressLabel) DOM.migProgressLabel.textContent = `Migration completed! 0 orphaned records, 100% integrity.`;
        if (DOM.btnExecuteMigration) DOM.btnExecuteMigration.style.display = 'none';
        if (DOM.btnViewIngestedTickets) DOM.btnViewIngestedTickets.style.display = 'inline-flex';

        showToast(`🎉 Migration Successful! Ingested tickets added to Incident Command.`, 'success');
      }
    }, 160);
  }

  // =========================================================================
  // CLASSIFICATION & PRIORITY MATRIX HELPERS
  // =========================================================================

  function populateClassificationDropdowns(catSelect, subSelect, itemSelect, initialCat, initialSub, initialItem) {
    if (!catSelect || !subSelect || !itemSelect) return;
    const taxonomy = (state && state.taxonomy) ? state.taxonomy : CLASSIFICATION_DATA;

    const catKeys = Object.keys(taxonomy);
    catSelect.innerHTML = catKeys.map(cat => 
      `<option value="${escapeHtml(cat)}"${cat === initialCat ? ' selected' : ''}>${escapeHtml(cat)}</option>`
    ).join('');

    const updateSubcategories = (selectedCat, preselectSub, preselectItem) => {
      const subcats = taxonomy[selectedCat] || {};
      const subcatKeys = Object.keys(subcats);
      subSelect.innerHTML = subcatKeys.map(sub => 
        `<option value="${escapeHtml(sub)}"${sub === preselectSub ? ' selected' : ''}>${escapeHtml(sub)}</option>`
      ).join('');
      const activeSub = preselectSub && subcats[preselectSub] ? preselectSub : subcatKeys[0];
      updateItems(selectedCat, activeSub, preselectItem);
    };

    const updateItems = (selectedCat, selectedSub, preselectItem) => {
      const items = (taxonomy[selectedCat] && taxonomy[selectedCat][selectedSub]) || [];
      itemSelect.innerHTML = items.map(itm => 
        `<option value="${escapeHtml(itm)}"${itm === preselectItem ? ' selected' : ''}>${escapeHtml(itm)}</option>`
      ).join('');
    };

    catSelect.onchange = () => {
      updateSubcategories(catSelect.value, null, null);
    };

    subSelect.onchange = () => {
      updateItems(catSelect.value, subSelect.value, null);
    };

    const activeCat = initialCat && taxonomy[initialCat] ? initialCat : catKeys[0];
    updateSubcategories(activeCat, initialSub, initialItem);
  }

  function setupPriorityMatrixCalculator(impactSelect, urgencySelect, badgeEl, labelEl, hiddenInput, onUpdate) {
    if (!impactSelect || !urgencySelect) return;

    function recalculate() {
      const impact = impactSelect.value;
      const urgency = urgencySelect.value;
      const calculatedP = calculatePriority(impact, urgency);

      if (badgeEl) {
        badgeEl.className = `priority-pill pill-${calculatedP.toLowerCase()}`;
        badgeEl.textContent = calculatedP;
      }
      if (labelEl) {
        labelEl.textContent = `${impact} × ${urgency} = ${calculatedP}`;
      }
      if (hiddenInput) {
        hiddenInput.value = calculatedP;
      }
      if (typeof onUpdate === 'function') {
        onUpdate(calculatedP, impact, urgency);
      }
    }

    impactSelect.addEventListener('change', recalculate);
    urgencySelect.addEventListener('change', recalculate);
    recalculate();
  }

  function formatMinutesToHours(totalMinutes) {
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    if (h > 0 && m > 0) return `${h}h ${m}m`;
    if (h > 0) return `${h}h`;
    return `${m}m`;
  }

  // =========================================================================
  // VIEW 4: RELATIONAL TICKET INSPECTION DRAWER (ZOHO SDP & GLPI SUITE)
  // =========================================================================

  function openTicketDrawer(ticketId) {
    const inc = state.incidents.find(i => i.id === ticketId);
    if (!inc) return;

    state.selectedTicket = inc;
    const ciObj = state.cmdbNodes.find(n => n.id === inc.ci);
    state.activeDrawerTab = state.activeDrawerTab || 'overview';

    // Worklogs calculation
    const totalLaborMinutes = (inc.worklogs || []).reduce((acc, w) => acc + ((Number(w.hours) || 0) * 60 + (Number(w.minutes) || 0)), 0);
    const totalLaborCost = (inc.worklogs || []).reduce((acc, w) => acc + (Number(w.cost) || 0), 0);
    const billableLaborCost = (inc.worklogs || []).filter(w => w.isBillable).reduce((acc, w) => acc + (Number(w.cost) || 0), 0);
    const billablePct = totalLaborCost > 0 ? Math.round((billableLaborCost / totalLaborCost) * 100) : 100;

    // Subtasks calculation
    const subtasksList = inc.subtasks || [];
    const completedSubtasks = subtasksList.filter(s => s.completed).length;
    const subtasksPct = subtasksList.length > 0 ? Math.round((completedSubtasks / subtasksList.length) * 100) : 0;

    // SLA Target Hours from policy
    const policyTargetHours = state.slaPolicies && state.slaPolicies[inc.priority] ? state.slaPolicies[inc.priority].resolveHours : (inc.priority === 'P1' ? 1 : 4);

    // Dynamic Lifecycle Transitions Buttons for Header Ribbon & Sidebar
    let ribbonActionBtn = '';
    let transitionsHtml = '';
    if (inc.status === 'NEW') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-start" id="ribbon-btn-start">▶ Start Work</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-start" id="trans-btn-start" title="Acknowledge, assign and begin active incident triage">▶ Assign &amp; Start Work</button>
        <button class="btn-transition btn-transition-hold" id="trans-btn-hold" title="Pause SLA clock and place on hold">⏸ Put on Hold</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Cancel or close ticket">✕ Close</button>
      `;
    } else if (inc.status === 'IN_PROGRESS') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-resolve" id="ribbon-btn-resolve">✓ Resolve Incident</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-hold" id="trans-btn-hold" title="Pause SLA clock and place on hold">⏸ Put on Hold</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        ${inc.priority !== 'P1' ? `<button class="btn-transition btn-transition-escalate" id="trans-btn-escalate" title="Escalate severity to P1 Critical">⚡ Escalate to P1</button>` : ''}
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Close incident">✕ Close</button>
      `;
    } else if (inc.status === 'ON_HOLD') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-start" id="ribbon-btn-resume">▶ Resume SLA</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-resume" id="trans-btn-resume" title="Resume active mitigation and unpause SLA timer">▶ Resume Work (Unpause SLA)</button>
        <button class="btn-transition btn-transition-resolve" id="trans-btn-resolve" title="Record resolution code and close out issue">✓ Resolve Ticket</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Close incident">✕ Close</button>
      `;
    } else if (inc.status === 'RESOLVED') {
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-reopen" id="ribbon-btn-reopen">⟲ Reopen</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-reopen" id="trans-btn-reopen" title="Reopen incident and restart mitigation">⟲ Reopen Incident</button>
        <button class="btn-transition btn-transition-close" id="trans-btn-close" title="Archive and close permanently">✕ Archive &amp; Close</button>
      `;
    } else { // CLOSED
      ribbonActionBtn = `<button class="btn-ribbon-action btn-ribbon-reopen" id="ribbon-btn-reopen">⟲ Reopen</button>`;
      transitionsHtml = `
        <button class="btn-transition btn-transition-reopen" id="trans-btn-reopen" title="Reopen incident">⟲ Reopen Incident</button>
      `;
    }

    // Status Ribbon CSS Class & Label
    let statusBadgeClass = 'status-badge-new';
    let statusLabel = 'New / Triaging';
    if (inc.status === 'IN_PROGRESS') { statusBadgeClass = 'status-badge-progress'; statusLabel = '⚡ In Progress'; }
    else if (inc.status === 'ON_HOLD') { statusBadgeClass = 'status-badge-hold'; statusLabel = `⏸ Paused (${escapeHtml(inc.holdReason || 'Hold')})`; }
    else if (inc.status === 'RESOLVED') { statusBadgeClass = 'status-badge-resolved'; statusLabel = '✓ Resolved'; }
    else if (inc.status === 'CLOSED') { statusBadgeClass = 'status-badge-closed'; statusLabel = 'Closed'; }

    // SLA Countdown text
    const slaText = (inc.status === 'RESOLVED') ? 'MET TARGET' : (inc.status === 'ON_HOLD' ? `PAUSED (${formatSlaTime(inc.slaSecondsRemaining)})` : formatSlaTime(inc.slaSecondsRemaining));

    const techniciansList = state.technicians || DEFAULT_TECHNICIANS;
    const defaultTechRate = techniciansList[0] ? techniciansList[0].rate : 150;

    DOM.drawerContentContainer.innerHTML = `
      <!-- 1. Top Drawer Command Ribbon -->
      <div class="drawer-command-ribbon">
        <div class="drawer-ribbon-left">
          <span class="drawer-ribbon-key-badge">${inc.id}</span>
          <span class="priority-pill pill-${inc.priority.toLowerCase()}" id="drawer-header-priority-pill">${inc.priority}</span>
          <span class="drawer-ribbon-status ${statusBadgeClass}">${statusLabel}</span>
          <span class="drawer-header-title-summary" title="${escapeHtml(inc.title)}">${escapeHtml(inc.title)}</span>
        </div>
        <div class="drawer-ribbon-actions">
          ${ribbonActionBtn}
          <button class="btn-icon-sm" id="btn-close-drawer" title="Close Drawer (Esc)">&times;</button>
        </div>
      </div>

      <!-- 2. Interactive KPI Glass HUD Strip (Zero Wall of White Text) -->
      <div class="drawer-kpi-hud-strip">
        <div class="kpi-hud-card" style="border-left: 3.5px solid ${inc.status === 'ON_HOLD' ? '#f59e0b' : inc.status === 'RESOLVED' ? '#10b981' : '#6366f1'};">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">SLA Resolution Target</span>
            <span class="kpi-hud-icon">${inc.status === 'ON_HOLD' ? '⏸️' : '⏱️'}</span>
          </div>
          <span class="kpi-hud-val font-mono ${inc.status === 'ON_HOLD' ? 'text-amber' : inc.status === 'RESOLVED' ? 'text-emerald' : 'text-indigo'}">${slaText}</span>
          <span class="kpi-hud-sub">Target: ${policyTargetHours}h • Paused: ${formatDurationShort(inc.totalPausedSeconds || 0)}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #f59e0b;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Priority Matrix</span>
            <span class="kpi-hud-icon">⚡</span>
          </div>
          <span class="kpi-hud-val">${inc.priority} Severity</span>
          <span class="kpi-hud-sub">${escapeHtml(inc.impact || 'Enterprise')} × ${escapeHtml(inc.urgency || 'High')}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #10b981;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Affected Service CI</span>
            <span class="kpi-hud-icon">🌐</span>
          </div>
          <span class="kpi-hud-val" style="font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(inc.ciName || inc.ci)}</span>
          <span class="kpi-hud-sub font-mono">Tier: ${ciObj ? ciObj.tier : '1'} • Provider: ${ciObj ? ciObj.provider : 'Cloud'}</span>
        </div>

        <div class="kpi-hud-card" style="border-left: 3.5px solid #0284c7;">
          <div class="kpi-hud-top">
            <span class="kpi-hud-title">Labor &amp; Subtasks</span>
            <span class="kpi-hud-icon">💵</span>
          </div>
          <span class="kpi-hud-val text-emerald font-mono">$${totalLaborCost.toFixed(2)}</span>
          <span class="kpi-hud-sub">${completedSubtasks}/${subtasksList.length} Tasks Done (${subtasksPct}%)</span>
        </div>
      </div>

      <!-- 3. Segmented Workspace Navigation Tabs (Left Column Focus) -->
      <div class="drawer-erp-workspace">
        
        <!-- Left Column: Tabbed Content Area -->
        <div class="drawer-col-left" style="padding: 0; background: #fafafa;">
          
          <!-- Tab Navigation Bar -->
          <div class="drawer-workspace-tabs">
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'overview' ? 'active' : ''}" data-drawer-tab="overview">
              <span>📋 Overview &amp; Diagnostics</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'subtasks' ? 'active' : ''}" data-drawer-tab="subtasks">
              <span>☑️ Action Checklist</span>
              <span class="drawer-tab-badge">${completedSubtasks}/${subtasksList.length}</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'worklogs' ? 'active' : ''}" data-drawer-tab="worklogs">
              <span>⏱️ Worklogs &amp; Costs</span>
              <span class="drawer-tab-badge font-mono">$${totalLaborCost.toFixed(0)}</span>
            </button>
            <button class="drawer-tab-btn ${state.activeDrawerTab === 'timeline' ? 'active' : ''}" data-drawer-tab="timeline">
              <span>📜 Audit Stream</span>
              <span class="drawer-tab-badge">${inc.timeline.length}</span>
            </button>
          </div>

          <div style="padding: 20px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
            
            <!-- TAB PANEL 1: Overview & Diagnostics -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'overview' ? 'active' : ''}" id="drawer-tab-overview">
              
              <!-- Executive Summary Card -->
              <div class="drawer-summary-card">
                <h3 class="drawer-summary-title">${escapeHtml(inc.title)}</h3>
                <div class="drawer-title-meta-row">
                  <span>Created: <strong>${inc.createdAt}</strong></span>
                  <span>•</span>
                  <span>AI Triage Confidence: <strong class="text-emerald font-mono">${inc.aiConfidence || '98.2%'}</strong></span>
                  <span>•</span>
                  <span>Caller: <span class="font-mono text-secondary">${escapeHtml(inc.caller)}</span></span>
                </div>
              </div>

              <!-- High-Contrast Dark Telemetry & Log Payload Box (Zero Wall of White Text) -->
              <div class="telemetry-code-block">
                <div class="telemetry-code-header">
                  <div class="telemetry-header-title">
                    <span class="telemetry-dot-red"></span>
                    <span class="telemetry-dot-yellow"></span>
                    <span class="telemetry-dot-green"></span>
                    <span>SYSTEM DIAGNOSTIC TELEMETRY &amp; STACK TRACE</span>
                  </div>
                  <button class="btn-copy-telemetry" id="btn-copy-telemetry-text">Copy Payload</button>
                </div>
                <div class="telemetry-code-content" id="telemetry-code-view">${escapeHtml(inc.description)}</div>
              </div>

              <!-- Autonomous AI Diagnostics Hub (Modern Interactive Tiles) -->
              <div class="erp-section-card" style="border: 1.5px solid #d8b4fe; background: linear-gradient(180deg, #faf5ff 0%, #ffffff 100%);">
                <div class="ai-copilot-top">
                  <div class="ai-copilot-title-group">
                    <span class="ai-star-sparkle">✦</span>
                    <h4 style="color:#581c87; font-weight:800;">Autonomous Sentinel-AI Action Hub</h4>
                  </div>
                  <span class="ai-copilot-badge">Real-time Heuristics</span>
                </div>
                <p class="ai-copilot-subtext">Click any intelligence action below to execute automated graph traversal, diagnostic synthesis, or executive communication drafting.</p>

                <div class="ai-tiles-grid">
                  <button class="btn-ai-tile" id="ai-btn-triage">
                    <span class="tile-icon">⚡</span>
                    <div class="tile-info">
                      <h5>Auto-Triage Analysis</h5>
                      <p>Neural root-cause hypothesis</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-blast">
                    <span class="tile-icon">🌐</span>
                    <div class="tile-info">
                      <h5>CMDB Blast Radius</h5>
                      <p>Traverse graph dependencies</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-runbook">
                    <span class="tile-icon">🛠️</span>
                    <div class="tile-info">
                      <h5>Synthesize Runbook</h5>
                      <p>Diagnostic commands &amp; steps</p>
                    </div>
                  </button>
                  <button class="btn-ai-tile" id="ai-btn-stakeholder">
                    <span class="tile-icon">📢</span>
                    <div class="tile-info">
                      <h5>Draft Stakeholder Update</h5>
                      <p>Customer &amp; leadership memo</p>
                    </div>
                  </button>
                </div>

                <div class="ai-output-box mt-3" id="drawer-ai-output" style="display: none;"></div>
              </div>

            </div>

            <!-- TAB PANEL 2: Remediation Checklist & Subtasks -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'subtasks' ? 'active' : ''}" id="drawer-tab-subtasks">
              <div class="erp-section-card">
                <div class="subtasks-progress-box">
                  <div class="progress-header-row">
                    <div class="drawer-section-title mb-0">
                      <span class="sec-icon">☑️</span>
                      <span>Remediation Action Items</span>
                    </div>
                    <span class="font-mono text-indigo font-bold text-xs" id="subtasks-header-count">${completedSubtasks} of ${subtasksList.length} Completed (${subtasksPct}%)</span>
                  </div>
                  <div class="subtasks-track mt-2">
                    <div class="subtasks-bar-fill" style="width: ${subtasksPct}%;"></div>
                  </div>
                </div>

                <!-- Add Subtask Form -->
                <form id="form-add-subtask" class="add-subtask-bar mt-3">
                  <input type="text" id="input-subtask-title" placeholder="Add checklist action (e.g. Verify DB read replicas, Flush cache)..." required>
                  <select id="input-subtask-assignee" class="zen-select" style="height:32px; font-size:11.5px;">
                    ${techniciansList.map(t => `<option value="${escapeHtml(t.name)}">${escapeHtml(t.name)}</option>`).join('')}
                    <option value="Unassigned">Unassigned</option>
                  </select>
                  <button type="submit" class="btn btn-sm btn-zen-primary">+ Add</button>
                </form>

                <!-- Subtasks List -->
                <div class="subtasks-items-list mt-3" id="subtasks-list-container">
                  ${subtasksList.length > 0 ? subtasksList.map(st => `
                    <div class="subtask-item ${st.completed ? 'completed' : ''}" data-subtask-id="${st.id}">
                      <div class="subtask-left">
                        <input type="checkbox" class="subtask-checkbox subtask-toggle" data-subtask-id="${st.id}" ${st.completed ? 'checked' : ''}>
                        <span class="subtask-title-text">${escapeHtml(st.title)}</span>
                      </div>
                      <div style="display:flex; align-items:center; gap:8px;">
                        <span class="subtask-assignee-pill">${escapeHtml(st.assignee)}</span>
                        <button class="btn-del-item btn-del-subtask" data-subtask-id="${st.id}" title="Remove subtask">&times;</button>
                      </div>
                    </div>
                  `).join('') : `
                    <div class="empty-subtasks-hint">
                      No subtasks yet. Add specific remediation steps above.
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- TAB PANEL 3: Worklogs & Labor Costing -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'worklogs' ? 'active' : ''}" id="drawer-tab-worklogs">
              <div class="erp-section-card">
                <div class="worklogs-summary-strip">
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Duration Logged</span>
                    <span class="wl-metric-val font-mono">${formatMinutesToHours(totalLaborMinutes)}</span>
                  </div>
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Total Labor Cost</span>
                    <span class="wl-metric-val font-mono text-emerald">$${totalLaborCost.toFixed(2)}</span>
                  </div>
                  <div class="worklog-summary-card">
                    <span class="wl-metric-label">Billing Ratio</span>
                    <span class="wl-metric-val font-mono text-indigo">${billablePct}% Billable</span>
                  </div>
                </div>

                <!-- Add Worklog Form -->
                <div class="add-worklog-card mt-3">
                  <div class="text-xs font-bold text-secondary mb-2">Log Technician Labor Hours</div>
                  <form id="form-add-worklog" style="display:flex; flex-direction:column; gap:8px;">
                    <div class="worklog-inputs-grid">
                      <div>
                        <label class="text-xs text-muted">Technician</label>
                        <select id="input-wl-tech" class="zen-select w-full" style="height:32px;">
                          ${techniciansList.map(t => `<option value="${escapeHtml(t.name)}" data-rate="${t.rate}">${escapeHtml(t.name)} ($${t.rate}/hr)</option>`).join('')}
                        </select>
                      </div>
                      <div style="display:flex; gap:6px;">
                        <div style="flex:1;">
                          <label class="text-xs text-muted">Hours</label>
                          <input type="number" id="input-wl-hours" class="zen-form-control" style="height:32px;" value="1" min="0" max="24">
                        </div>
                        <div style="flex:1;">
                          <label class="text-xs text-muted">Mins</label>
                          <select id="input-wl-mins" class="zen-select w-full" style="height:32px;">
                            <option value="0">0m</option>
                            <option value="15">15m</option>
                            <option value="30" selected>30m</option>
                            <option value="45">45m</option>
                          </select>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-muted">Hourly Rate ($/hr)</label>
                        <input type="number" id="input-wl-rate" class="zen-form-control font-mono" style="height:32px;" value="${defaultTechRate}" min="0" step="5">
                      </div>
                    </div>

                    <div>
                      <label class="text-xs text-muted">Work Description / Remediation Notes</label>
                      <input type="text" id="input-wl-desc" class="zen-form-control" placeholder="Describe actions performed during this labor window..." required>
                    </div>

                    <div style="display:flex; align-items:center; justify-content:space-between; margin-top:4px;">
                      <label style="display:inline-flex; align-items:center; gap:6px; font-size:12px; cursor:pointer;">
                        <input type="checkbox" id="check-wl-billable" checked class="zen-checkbox">
                        <span>Billable to department cost center</span>
                      </label>
                      <button type="submit" class="btn btn-sm btn-zen-primary">
                        <span>+ Log Labor Entry</span>
                      </button>
                    </div>
                  </form>
                </div>

                <!-- Worklogs List -->
                <div class="worklog-entries-list mt-3" id="worklogs-list-container">
                  ${(inc.worklogs && inc.worklogs.length > 0) ? inc.worklogs.map(w => `
                    <div class="worklog-row-item">
                      <div class="worklog-row-header">
                        <div class="worklog-tech-badge">
                          <span class="tech-avatar-mini">${escapeHtml(w.technician.substring(0, 2).toUpperCase())}</span>
                          <span>${escapeHtml(w.technician)}</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                          <span class="worklog-cost-pill">$${Number(w.cost).toFixed(2)}</span>
                          <button class="btn-del-item btn-del-worklog" data-wl-id="${w.id}" title="Remove entry">&times;</button>
                        </div>
                      </div>
                      <div class="worklog-meta-line">
                        <span class="font-mono"><strong>${w.hours}h ${w.minutes}m</strong> (@ $${w.rate}/hr)</span>
                        <span>•</span>
                        <span class="${w.isBillable ? 'badge-billable' : 'badge-nonbillable'}">${w.isBillable ? 'Billable' : 'Non-Billable'}</span>
                        <span>•</span>
                        <span>${w.loggedAt}</span>
                      </div>
                      <div class="worklog-desc-text">${escapeHtml(w.description)}</div>
                    </div>
                  `).join('') : `
                    <div class="empty-worklogs-hint">
                      No labor hours recorded yet. Use the form above to track technician time and costs.
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- TAB PANEL 4: Activity & Audit Timeline Stream -->
            <div class="drawer-tab-panel ${state.activeDrawerTab === 'timeline' ? 'active' : ''}" id="drawer-tab-timeline">
              <div class="erp-section-card">
                <div class="drawer-section-title">
                  <span class="sec-icon">📜</span>
                  <span>Incident Audit Stream (${inc.timeline.length} Entries)</span>
                </div>

                <div class="timeline-list" id="drawer-timeline-list">
                  ${inc.timeline.map(t => `
                    <div class="timeline-item">
                      <span class="timeline-bullet ${t.isAi ? 'bullet-ai' : ''}"></span>
                      <div class="timeline-item-meta">
                        <strong>${escapeHtml(t.user)}</strong> • ${t.time}
                      </div>
                      <div class="timeline-item-body">${escapeHtml(t.text)}</div>
                    </div>
                  `).join('')}
                </div>

                <div class="add-comment-row mt-3">
                  <input type="text" id="input-drawer-comment" class="add-comment-input" placeholder="Add work note or stakeholder update...">
                  <button class="btn btn-sm btn-zen-primary" id="btn-add-drawer-comment">Log Note</button>
                </div>
              </div>
            </div>

          </div>
        </div>

        <!-- ======================================================== -->
        <!-- RIGHT COLUMN: Governance, People, Classification & CI    -->
        <!-- ======================================================== -->
        <div class="drawer-col-right">
          
          <!-- Lifecycle State Machine Flow Card -->
          <div class="drawer-side-card side-card-accent-indigo">
            <div class="side-card-header">
              <span class="side-card-title">STATUS &amp; LIFECYCLE ACTION</span>
            </div>
            <div>
              <label class="text-xs text-muted">Current ITIL Status</label>
              <select id="drawer-status-select" class="zen-select w-full" style="height:32px; font-weight:700; margin-top:3px;">
                <option value="NEW" ${inc.status === 'NEW' ? 'selected' : ''}>New / Triaging</option>
                <option value="IN_PROGRESS" ${inc.status === 'IN_PROGRESS' ? 'selected' : ''}>In Progress / Mitigating</option>
                <option value="ON_HOLD" ${inc.status === 'ON_HOLD' ? 'selected' : ''}>On Hold / SLA Paused</option>
                <option value="RESOLVED" ${inc.status === 'RESOLVED' ? 'selected' : ''}>Resolved / Mitigated</option>
                <option value="CLOSED" ${inc.status === 'CLOSED' ? 'selected' : ''}>Closed / Archived</option>
              </select>
            </div>
            <div class="mt-3">
              <span class="text-xs text-muted mb-1" style="display:block;">Allowed Actions:</span>
              <div class="transition-actions-row">
                ${transitionsHtml}
              </div>
            </div>
          </div>

          <!-- People & Ownership Card -->
          <div class="drawer-side-card side-card-accent-sky">
            <div class="side-card-header">
              <span class="side-card-title">PEOPLE &amp; ESCALATION</span>
            </div>
            <div class="caller-profile-row">
              <div class="tech-avatar-mini" style="width:34px; height:34px; font-size:13px; background:#4f46e5; color:white;">
                ${escapeHtml((inc.caller || 'AR').substring(0, 2).toUpperCase())}
              </div>
              <div class="caller-details">
                <strong>${escapeHtml(inc.caller || 'alex.rivera@opennow.io')}</strong>
                <span class="text-xs text-muted">Site Reliability Engineering</span>
              </div>
            </div>
            <div class="assignment-meta-lines mt-3">
              <div class="pair-row"><span class="pair-k">Assignment Group:</span><strong class="pair-v text-indigo">${escapeHtml(inc.team)}</strong></div>
              <div class="pair-row"><span class="pair-k">Primary Lead:</span><span class="pair-v">Alex Rivera (Lead)</span></div>
              <div class="pair-row"><span class="pair-k">ITIL State:</span><span class="pair-v font-bold ${inc.status === 'ON_HOLD' ? 'text-amber' : inc.status === 'RESOLVED' ? 'text-emerald' : 'text-indigo'}">${formatStatusLabel(inc.status)}</span></div>
            </div>
          </div>

          <!-- Three-Tier ITIL Classification Card -->
          <div class="drawer-side-card side-card-accent-emerald">
            <div class="side-card-header">
              <span class="side-card-title">3-TIER TAXONOMY</span>
              <span class="badge-tag">ITIL 4</span>
            </div>
            <div class="classification-vertical-stack">
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Category</label>
                <select id="drawer-cat-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Subcategory</label>
                <select id="drawer-subcat-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
              <div class="form-group">
                <label class="text-xs text-muted">Item</label>
                <select id="drawer-item-select" class="zen-select w-full" style="height:30px;"></select>
              </div>
            </div>
          </div>

          <!-- Priority Matrix Card -->
          <div class="drawer-side-card side-card-accent-amber">
            <div class="side-card-header">
              <span class="side-card-title">PRIORITY MATRIX</span>
              <span class="priority-pill pill-${inc.priority.toLowerCase()}" id="drawer-matrix-badge">${inc.priority}</span>
            </div>
            <div class="matrix-inputs-stack">
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Impact</label>
                <select id="drawer-impact-select" class="zen-select w-full" style="height:30px;">
                  <option value="Enterprise" ${inc.impact === 'Enterprise' ? 'selected' : ''}>Enterprise (High / Org-wide)</option>
                  <option value="Department" ${inc.impact === 'Department' ? 'selected' : ''}>Department (Medium / Service)</option>
                  <option value="Single User" ${inc.impact === 'Single User' ? 'selected' : ''}>Single User (Low / Localized)</option>
                </select>
              </div>
              <div class="form-group mb-2">
                <label class="text-xs text-muted">Urgency</label>
                <select id="drawer-urgency-select" class="zen-select w-full" style="height:30px;">
                  <option value="Critical" ${inc.urgency === 'Critical' ? 'selected' : ''}>Critical (Immediate Outage)</option>
                  <option value="High" ${inc.urgency === 'High' ? 'selected' : ''}>High (Severe Disruption)</option>
                  <option value="Medium" ${inc.urgency === 'Medium' ? 'selected' : ''}>Medium (Workaround Exists)</option>
                  <option value="Low" ${inc.urgency === 'Low' ? 'selected' : ''}>Low (Minor / Inquiry)</option>
                </select>
              </div>
              <div class="matrix-calc-result-box">
                <span class="matrix-calc-label" id="drawer-matrix-label">${inc.impact || 'Enterprise'} × ${inc.urgency || 'High'} = ${inc.priority}</span>
              </div>
            </div>
          </div>

          <!-- Affected CI & Topology Dependencies -->
          <div class="drawer-side-card">
            <div class="side-card-header">
              <span class="side-card-title">AFFECTED CI &amp; TOPOLOGY</span>
              <span class="badge-tag">${ciObj ? ciObj.tier : 'Service'}</span>
            </div>
            <div class="ci-summary-box">
              <div class="ci-title-link" id="drawer-jump-ci" title="Click to inspect node in CMDB Topology Graph">
                <span class="ci-name font-bold text-indigo">${escapeHtml(inc.ciName || inc.ci)}</span>
                <span class="ci-jump-icon">➔</span>
              </div>
              <div class="ci-submeta font-mono text-xs text-muted mt-1">
                ID: ${inc.ci} • Provider: ${ciObj ? ciObj.provider : 'Cloud AWS'}
              </div>
              
              <div class="ci-dep-links mt-3">
                <div class="dep-link-label text-xs text-muted">Upstream Callers:</div>
                <div class="dep-chips-list-sm mt-1">
                  ${(ciObj && ciObj.upstream && ciObj.upstream.length > 0) ? ciObj.upstream.map(u => `<span class="ci-dep-chip">${u}</span>`).join('') : '<span class="text-xs text-muted">No upstream callers (Edge origin)</span>'}
                </div>

                <div class="dep-link-label text-xs text-muted mt-2">Downstream Dependencies:</div>
                <div class="dep-chips-list-sm mt-1">
                  ${(ciObj && ciObj.downstream && ciObj.downstream.length > 0) ? ciObj.downstream.map(d => `<span class="ci-dep-chip chip-downstream">${d}</span>`).join('') : '<span class="text-xs text-muted">Terminal dependency</span>'}
                </div>
              </div>
            </div>
          </div>

          <!-- Resolution Verification Card (if resolved) -->
          ${inc.status === 'RESOLVED' ? `
            <div class="drawer-side-card" style="background:#ecfdf5; border-color:#a7f3d0;">
              <div class="side-card-header" style="border-bottom-color:#a7f3d0;">
                <span class="side-card-title text-emerald">✓ RESOLUTION DETAILS</span>
                <span class="badge-tag text-emerald">${escapeHtml(inc.resolutionCode || 'Resolved')}</span>
              </div>
              <div class="text-xs" style="color:#065f46; line-height:1.45;">
                <p><strong>Root Cause:</strong> ${escapeHtml(inc.rootCause || 'Root cause eliminated.')}</p>
                ${inc.preventiveAction ? `<p class="mt-2"><strong>Preventive Action:</strong> ${escapeHtml(inc.preventiveAction)}</p>` : ''}
                <p class="mt-2"><strong>FCR:</strong> ${inc.isFcr ? 'Yes (First Call Resolution)' : 'No (Escalated)'}</p>
                <p class="mt-1 text-muted">Resolved at: ${inc.resolvedAt || 'Recently'}</p>
              </div>
            </div>
          ` : ''}

          <!-- On Hold Justification Card (if on hold) -->
          ${inc.status === 'ON_HOLD' ? `
            <div class="drawer-side-card" style="background:#fffbeb; border-color:#fde68a;">
              <div class="side-card-header" style="border-bottom-color:#fde68a;">
                <span class="side-card-title text-amber">⏸️ HOLD JUSTIFICATION</span>
                <span class="badge-tag text-amber">${escapeHtml(inc.holdReason || 'Pending Input')}</span>
              </div>
              <div class="text-xs" style="color:#92400e; line-height:1.45;">
                <p><strong>Justification:</strong> ${escapeHtml(inc.holdNotes || 'Work paused awaiting external dependency.')}</p>
                <p class="mt-2"><strong>Total SLA Time Frozen:</strong> ${formatDurationShort(inc.totalPausedSeconds || 0)}</p>
              </div>
            </div>
          ` : ''}

        </div>
      </div>
    `;

    // Bind Workspace Tabs Navigation
    document.querySelectorAll('.drawer-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tabName = btn.getAttribute('data-drawer-tab');
        state.activeDrawerTab = tabName;
        document.querySelectorAll('.drawer-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.drawer-tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const targetPanel = document.getElementById(`drawer-tab-${tabName}`);
        if (targetPanel) targetPanel.classList.add('active');
      });
    });

    // Bind Copy Telemetry Button
    const btnCopy = document.getElementById('btn-copy-telemetry-text');
    if (btnCopy) {
      btnCopy.addEventListener('click', () => {
        navigator.clipboard.writeText(inc.description);
        btnCopy.textContent = 'Copied!';
        setTimeout(() => { btnCopy.textContent = 'Copy Payload'; }, 1800);
      });
    }

    // Bind Close Button & Backdrop
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeTicketDrawer);
    DOM.drawerBackdrop.classList.add('active');
    DOM.ticketSlideover.classList.add('open');

    // Bind Quick Action Ribbon Buttons
    const ribbonStart = document.getElementById('ribbon-btn-start');
    if (ribbonStart) {
      ribbonStart.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Began mitigation via quick ribbon action.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Work started on ${inc.id}. Status: In Progress.`, 'success');
      });
    }
    const ribbonResolve = document.getElementById('ribbon-btn-resolve');
    if (ribbonResolve) ribbonResolve.addEventListener('click', () => openResolutionModal(inc.id));
    const ribbonResume = document.getElementById('ribbon-btn-resume');
    if (ribbonResume) {
      ribbonResume.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Resumed mitigation from hold via ribbon.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Mitigation resumed on ${inc.id}. SLA unpaused.`, 'success');
      });
    }
    const ribbonReopen = document.getElementById('ribbon-btn-reopen');
    if (ribbonReopen) {
      ribbonReopen.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        if (inc.slaSecondsRemaining <= 0) inc.slaSecondsRemaining = 3600;
        inc.timeline.unshift({ time: 'Just now', user: 'Alex Rivera (SRE)', text: 'Reopened incident via ribbon action.' });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} reopened!`, 'warning');
      });
    }

    // Bind Jump to CI
    const jumpCi = document.getElementById('drawer-jump-ci');
    if (jumpCi) {
      jumpCi.addEventListener('click', () => {
        closeTicketDrawer();
        switchView('cmdb-topology');
        openCmdbInspector(inc.ci);
      });
    }

    // Populate Cascading Classification in Drawer
    const drawerCat = document.getElementById('drawer-cat-select');
    const drawerSubcat = document.getElementById('drawer-subcat-select');
    const drawerItem = document.getElementById('drawer-item-select');
    if (drawerCat && drawerSubcat && drawerItem) {
      populateClassificationDropdowns(drawerCat, drawerSubcat, drawerItem, inc.category, inc.subcategory, inc.item);
      const onClassChange = () => {
        inc.category = drawerCat.value;
        inc.subcategory = drawerSubcat.value;
        inc.item = drawerItem.value;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: `Updated classification to: ${inc.category} ➔ ${inc.subcategory} ➔ ${inc.item}.`
        });
        showToast('Classification updated successfully.', 'info');
      };
      drawerCat.addEventListener('change', onClassChange);
      drawerSubcat.addEventListener('change', onClassChange);
      drawerItem.addEventListener('change', onClassChange);
    }

    // Setup Priority Matrix Calculator in Drawer
    const drawerImpact = document.getElementById('drawer-impact-select');
    const drawerUrgency = document.getElementById('drawer-urgency-select');
    const drawerMatrixBadge = document.getElementById('drawer-matrix-badge');
    const drawerMatrixLabel = document.getElementById('drawer-matrix-label');
    if (drawerImpact && drawerUrgency) {
      setupPriorityMatrixCalculator(drawerImpact, drawerUrgency, drawerMatrixBadge, drawerMatrixLabel, null, (calcP, imp, urg) => {
        if (inc.priority !== calcP || inc.impact !== imp || inc.urgency !== urg) {
          const oldP = inc.priority;
          inc.impact = imp;
          inc.urgency = urg;
          inc.priority = calcP;
          const headerBadge = document.getElementById('drawer-header-priority-pill');
          if (headerBadge) {
            headerBadge.className = `priority-pill pill-${calcP.toLowerCase()}`;
            headerBadge.textContent = calcP;
          }
          if (oldP !== calcP) {
            inc.timeline.unshift({
              time: 'Just now',
              user: 'Alex Rivera (SRE)',
              text: `Recalculated priority: ${oldP} ➔ ${calcP} based on Impact: ${imp}, Urgency: ${urg}.`
            });
            renderTickets();
            showToast(`Priority recalculated to ${calcP}`, 'info');
          }
        }
      });
    }

    // Lifecycle Action Bar Button Listeners
    const btnStart = document.getElementById('trans-btn-start');
    if (btnStart) {
      btnStart.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Assigned incident and began active mitigation. SLA countdown started.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Work started on ${inc.id}. Status: In Progress.`, 'success');
      });
    }

    const btnHold = document.getElementById('trans-btn-hold');
    if (btnHold) {
      btnHold.addEventListener('click', () => {
        openHoldModal(inc.id);
      });
    }

    const btnResume = document.getElementById('trans-btn-resume');
    if (btnResume) {
      btnResume.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Resumed mitigation from hold. Active SLA clock resumed.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Mitigation resumed on ${inc.id}. SLA unpaused.`, 'success');
      });
    }

    const btnResolve = document.getElementById('trans-btn-resolve');
    if (btnResolve) {
      btnResolve.addEventListener('click', () => {
        openResolutionModal(inc.id);
      });
    }

    const btnClose = document.getElementById('trans-btn-close');
    if (btnClose) {
      btnClose.addEventListener('click', () => {
        inc.status = 'CLOSED';
        inc.isPaused = false;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Incident closed and permanently archived.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} closed.`, 'info');
      });
    }

    const btnReopen = document.getElementById('trans-btn-reopen');
    if (btnReopen) {
      btnReopen.addEventListener('click', () => {
        inc.status = 'IN_PROGRESS';
        inc.isPaused = false;
        if (inc.slaSecondsRemaining <= 0) inc.slaSecondsRemaining = 3600;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Reopened incident. SLA timer restarted.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`Incident ${inc.id} reopened!`, 'warning');
      });
    }

    const btnEscalate = document.getElementById('trans-btn-escalate');
    if (btnEscalate) {
      btnEscalate.addEventListener('click', () => {
        inc.priority = 'P1';
        inc.impact = 'Enterprise';
        inc.urgency = 'Critical';
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: 'Manually escalated incident to P1 Critical severity.'
        });
        renderTickets();
        openTicketDrawer(inc.id);
        showToast(`🚨 ${inc.id} escalated to P1 Critical!`, 'error');
      });
    }

    // Status select change
    const statusSelect = document.getElementById('drawer-status-select');
    if (statusSelect) {
      statusSelect.addEventListener('change', (e) => {
        const newStatus = e.target.value;
        if (newStatus === 'RESOLVED') {
          openResolutionModal(inc.id);
        } else if (newStatus === 'ON_HOLD') {
          openHoldModal(inc.id);
        } else {
          inc.status = newStatus;
          inc.isPaused = false;
          inc.timeline.unshift({
            time: 'Just now',
            user: 'Alex Rivera (SRE)',
            text: `Changed status to ${formatStatusLabel(newStatus)}.`
          });
          renderTickets();
          openTicketDrawer(inc.id);
          showToast(`${inc.id} status updated to ${formatStatusLabel(newStatus)}`, 'success');
        }
      });
    }

    // Worklog Technician select auto-rate binding
    const wlTechSelect = document.getElementById('input-wl-tech');
    const wlRateInput = document.getElementById('input-wl-rate');
    if (wlTechSelect && wlRateInput) {
      wlTechSelect.addEventListener('change', () => {
        const selectedOpt = wlTechSelect.options[wlTechSelect.selectedIndex];
        const r = selectedOpt ? selectedOpt.getAttribute('data-rate') : null;
        if (r) wlRateInput.value = r;
      });
    }

    // Worklogs Form Submit
    const formWl = document.getElementById('form-add-worklog');
    if (formWl) {
      formWl.addEventListener('submit', (e) => {
        e.preventDefault();
        const tech = document.getElementById('input-wl-tech').value;
        const hours = parseInt(document.getElementById('input-wl-hours').value, 10) || 0;
        const mins = parseInt(document.getElementById('input-wl-mins').value, 10) || 0;
        const rate = parseFloat(document.getElementById('input-wl-rate').value) || 150;
        const desc = document.getElementById('input-wl-desc').value.trim();
        const isBillable = document.getElementById('check-wl-billable').checked;

        if (hours === 0 && mins === 0) {
          showToast('Please enter at least 15 minutes of work time.', 'error');
          return;
        }

        const cost = ((hours + mins / 60) * rate);
        const newWl = {
          id: `WL-${Date.now()}`,
          technician: tech,
          hours: hours,
          minutes: mins,
          rate: rate,
          cost: parseFloat(cost.toFixed(2)),
          isBillable: isBillable,
          description: desc,
          loggedAt: 'Just now'
        };

        if (!inc.worklogs) inc.worklogs = [];
        inc.worklogs.unshift(newWl);

        inc.timeline.unshift({
          time: 'Just now',
          user: tech,
          text: `Logged ${hours}h ${mins}m labor ($${cost.toFixed(2)}): ${desc}`
        });

        openTicketDrawer(inc.id);
        showToast(`⏱️ Logged ${hours}h ${mins}m ($${cost.toFixed(2)}) labor cost.`, 'success');
      });
    }

    // Delete Worklog entry
    document.querySelectorAll('.btn-del-worklog').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const wlId = btn.getAttribute('data-wl-id');
        inc.worklogs = (inc.worklogs || []).filter(w => w.id !== wlId);
        openTicketDrawer(inc.id);
        showToast('Worklog entry removed.', 'info');
      });
    });

    // Subtasks Add Submit
    const formSubtask = document.getElementById('form-add-subtask');
    if (formSubtask) {
      formSubtask.addEventListener('submit', (e) => {
        e.preventDefault();
        const title = document.getElementById('input-subtask-title').value.trim();
        const assignee = document.getElementById('input-subtask-assignee').value;
        if (!title) return;

        const newSt = {
          id: `SUB-${Date.now()}`,
          title: title,
          assignee: assignee,
          completed: false,
          completedAt: null
        };

        if (!inc.subtasks) inc.subtasks = [];
        inc.subtasks.push(newSt);

        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: `Added checklist subtask: "${title}" assigned to ${assignee}.`
        });

        openTicketDrawer(inc.id);
        showToast(`Added checklist subtask.`, 'success');
      });
    }

    // Toggle Subtask Checkbox
    document.querySelectorAll('.subtask-toggle').forEach(chk => {
      chk.addEventListener('change', () => {
        const stId = chk.getAttribute('data-subtask-id');
        const st = (inc.subtasks || []).find(s => s.id === stId);
        if (st) {
          st.completed = chk.checked;
          st.completedAt = chk.checked ? 'Just now' : null;
          inc.timeline.unshift({
            time: 'Just now',
            user: 'Alex Rivera (SRE)',
            text: `${st.completed ? 'Completed' : 'Unchecked'} checklist task: "${st.title}".`
          });
          openTicketDrawer(inc.id);
          showToast(st.completed ? '✓ Subtask marked complete.' : 'Subtask unchecked.', 'info');
        }
      });
    });

    // Delete Subtask
    document.querySelectorAll('.btn-del-subtask').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const stId = btn.getAttribute('data-subtask-id');
        inc.subtasks = (inc.subtasks || []).filter(s => s.id !== stId);
        openTicketDrawer(inc.id);
        showToast('Subtask removed from checklist.', 'info');
      });
    });

    // Activity Timeline Comment Add
    const commentInput = document.getElementById('input-drawer-comment');
    const commentBtn = document.getElementById('btn-add-drawer-comment');
    if (commentBtn && commentInput) {
      const submitComment = () => {
        const text = commentInput.value.trim();
        if (!text) return;
        inc.timeline.unshift({
          time: 'Just now',
          user: 'Alex Rivera (SRE)',
          text: text
        });
        commentInput.value = '';
        openTicketDrawer(inc.id);
        showToast('Work note logged to timeline.', 'info');
      };
      commentBtn.addEventListener('click', submitComment);
      commentInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitComment();
      });
    }

    bindAiCopilotButtons(inc);
  }


  function closeTicketDrawer() {
    DOM.ticketSlideover.classList.remove('open');
    DOM.drawerBackdrop.classList.remove('active');
  }

  function bindAiCopilotButtons(inc) {
    const outputBox = document.getElementById('drawer-ai-output');
    if (!outputBox) return;

    const btnTriage = document.getElementById('ai-btn-triage');
    if (btnTriage) {
      btnTriage.addEventListener('click', () => {
        outputBox.style.display = 'flex';
        outputBox.innerHTML = `
          <h5>✦ AI Triage Intelligence (Confidence: 98.4%)</h5>
          <p><strong>Predicted Root Cause:</strong> Severe lock contention on database table caused by unindexed batch query or uncommitted transaction.</p>
          <p><strong>Recommended Priority:</strong> <span class="priority-pill pill-p1">P1 Critical</span> (Direct checkout cascade detected).</p>
          <p><strong>Recommended Assignment:</strong> Database-Ops (Primary on-call: @david-chen)</p>
          <button class="btn btn-sm btn-zen-primary mt-2" id="btn-apply-triage">Apply AI Recommendations to Incident</button>
        `;

        const applyBtn = document.getElementById('btn-apply-triage');
        if (applyBtn) {
          applyBtn.addEventListener('click', () => {
            inc.aiTriageDone = true;
            inc.priority = 'P1';
            inc.impact = 'Enterprise';
            inc.urgency = 'Critical';
            inc.team = 'Database-Ops';
            inc.timeline.unshift({
              time: 'Just now',
              user: 'AI Co-Pilot',
              text: 'Applied AI Triage recommendations: Escalated to P1, assigned to Database-Ops.',
              isAi: true
            });
            renderTickets();
            openTicketDrawer(inc.id);
            showToast('AI Triage applied to ticket successfully.', 'success');
          });
        }
      });
    }

    const btnBlast = document.getElementById('ai-btn-blast');
    if (btnBlast) {
      btnBlast.addEventListener('click', () => {
        outputBox.style.display = 'flex';
        outputBox.innerHTML = `
          <h5>✦ CMDB Graph Blast Radius Solver</h5>
          <p>Traversed downstream dependency mesh for <strong>${escapeHtml(inc.ciName)}</strong>:</p>
          <ul style="padding-left: 18px; margin: 4px 0; color: #475569;">
            <li><strong>Direct Dependents:</strong> Payment Gateway Service (CI-PAY-003)</li>
            <li><strong>Second-Order Impact:</strong> Kong API Gateway Ingress (CI-INGRESS-005)</li>
            <li><strong>Third-Order Impact:</strong> Customer Checkout Flow (Global Anycast Edge)</li>
          </ul>
          <div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: 6px; padding: 8px 10px; margin-top: 6px;">
            <strong class="text-rose">Estimated Business Exposure:</strong> ~$1,420/min revenue delay • 1,280 active checkout sessions stalled.
          </div>
          <button class="btn btn-sm btn-warning-outline mt-2" id="btn-view-graph-impact">Inspect Blast Radius on CMDB Topology →</button>
        `;

        const viewGraphBtn = document.getElementById('btn-view-graph-impact');
        if (viewGraphBtn) {
          viewGraphBtn.addEventListener('click', () => {
            closeTicketDrawer();
            switchView('cmdb-topology');
            toggleBlastRadiusSimulation();
          });
        }
      });
    }

    const btnRunbook = document.getElementById('ai-btn-runbook');
    if (btnRunbook) {
      btnRunbook.addEventListener('click', () => {
        outputBox.style.display = 'flex';
        outputBox.innerHTML = `
          <h5>✦ Autonomous Runbook Synthesizer</h5>
          <p>Step 1: Terminate blocking connection holding RowExclusiveLock in terminal:</p>
          <div class="ai-command-snippet">
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle in transaction' 
  AND query_start < NOW() - INTERVAL '2 minutes';
          </div>
          <p class="mt-2 text-sm text-secondary">Step 2: Emergency scale-out on PgBouncer connection pooler:</p>
          <div class="ai-command-snippet">
kubectl scale deployment/pgbouncer --replicas=6 -n database
          </div>
          <div class="form-row-2 mt-2">
            <button class="btn btn-sm btn-zen-outline" id="btn-copy-runbook">Copy Commands</button>
            <button class="btn btn-sm btn-zen-primary" id="btn-execute-runbook">Log Runbook in Activity</button>
          </div>
        `;

        const copyBtn = document.getElementById('btn-copy-runbook');
        if (copyBtn) {
          copyBtn.addEventListener('click', () => {
            showToast('Runbook shell commands copied to clipboard!', 'success');
          });
        }

        const execBtn = document.getElementById('btn-execute-runbook');
        if (execBtn) {
          execBtn.addEventListener('click', () => {
            inc.timeline.unshift({
              time: 'Just now',
              user: 'AI Runbook Synthesizer',
              text: 'Generated and verified emergency remediation runbook: Terminate idle lock transaction and scale PgBouncer.',
              isAi: true
            });
            openTicketDrawer(inc.id);
            showToast('Runbook logged to incident audit timeline.', 'info');
          });
        }
      });
    }

    const btnStakeholder = document.getElementById('ai-btn-stakeholder');
    if (btnStakeholder) {
      btnStakeholder.addEventListener('click', () => {
        outputBox.style.display = 'flex';
        outputBox.innerHTML = `
          <h5>✦ Stakeholder &amp; Statuspage Communications Draft</h5>
          <div class="drawer-desc-box" style="font-size:12px; margin-top:6px;">
<strong>INCIDENT UPDATE: [Investigating] Payment &amp; Database Degradation</strong>

• <strong>Summary:</strong> SRE and Database teams are actively addressing latency and connection timeouts affecting checkout.
• <strong>Impact:</strong> A subset of users may experience delayed payment confirmations.
• <strong>Actions in Progress:</strong> Emergency connection pool recycling initiated; failover replica standing by.
• <strong>Next Update:</strong> Within 20 minutes (at ${new Date(Date.now() + 20 * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}).
          </div>
          <button class="btn btn-sm btn-zen-primary mt-2" id="btn-copy-stakeholder">Copy to Clipboard (Slack / Statuspage)</button>
        `;

        const copyStakeholder = document.getElementById('btn-copy-stakeholder');
        if (copyStakeholder) {
          copyStakeholder.addEventListener('click', () => {
            showToast('Stakeholder update copied to clipboard!', 'success');
          });
        }
      });
    }
  }

  // =========================================================================
  // VIEW 5: RESOLUTION & HOLD MODALS (ITIL INCIDENT MANAGEMENT)
  // =========================================================================

  function openResolutionModal(ticketId) {
    const inc = state.incidents.find(i => i.id === ticketId);
    if (!inc) return;

    refreshResolutionCodesInUI();

    if (DOM.resolveTicketId) DOM.resolveTicketId.value = inc.id;
    if (DOM.resModalTitle) DOM.resModalTitle.textContent = `Resolve Incident ${inc.id}`;
    if (DOM.selectResolutionCode) DOM.selectResolutionCode.value = inc.resolutionCode || 'Software Patch / Deploy';
    if (DOM.inputRootCause) DOM.inputRootCause.value = inc.rootCause || '';
    if (DOM.inputPreventiveAction) DOM.inputPreventiveAction.value = inc.preventiveAction || '';
    if (DOM.checkFcr) DOM.checkFcr.checked = inc.isFcr || false;

    if (DOM.resolutionModalBackdrop) DOM.resolutionModalBackdrop.classList.add('open');
  }

  function closeResolutionModal() {
    if (DOM.resolutionModalBackdrop) DOM.resolutionModalBackdrop.classList.remove('open');
  }

  function handleResolutionSubmit(e) {
    e.preventDefault();
    const id = DOM.resolveTicketId.value;
    const inc = state.incidents.find(i => i.id === id);
    if (!inc) return;

    const resCode = DOM.selectResolutionCode.value;
    const rootCause = DOM.inputRootCause.value.trim();
    const prevAction = DOM.inputPreventiveAction ? DOM.inputPreventiveAction.value.trim() : '';
    const isFcr = DOM.checkFcr ? DOM.checkFcr.checked : false;

    inc.status = 'RESOLVED';
    inc.isPaused = false;
    inc.resolutionCode = resCode;
    inc.rootCause = rootCause;
    inc.preventiveAction = prevAction;
    inc.isFcr = isFcr;
    inc.resolvedAt = 'Just now';

    inc.timeline.unshift({
      time: 'Just now',
      user: 'Alex Rivera (SRE)',
      text: `Incident resolved: [${resCode}]. FCR: ${isFcr ? 'Yes' : 'No'}. Root Cause: ${rootCause}`
    });

    closeResolutionModal();
    renderTickets();
    if (state.selectedTicket && state.selectedTicket.id === id) {
      openTicketDrawer(id);
    }
    showToast(`🎉 Incident ${id} resolved with ${resCode}!`, 'success');
  }

  function openHoldModal(ticketId) {
    const inc = state.incidents.find(i => i.id === ticketId);
    if (!inc) return;

    if (DOM.holdTicketId) DOM.holdTicketId.value = inc.id;
    if (DOM.holdModalTitle) DOM.holdModalTitle.textContent = `Put Incident ${inc.id} on Hold`;
    if (DOM.selectHoldReason) DOM.selectHoldReason.value = inc.holdReason || 'Pending Customer';
    if (DOM.inputHoldNotes) DOM.inputHoldNotes.value = inc.holdNotes || '';

    if (DOM.holdModalBackdrop) DOM.holdModalBackdrop.classList.add('open');
  }

  function closeHoldModal() {
    if (DOM.holdModalBackdrop) DOM.holdModalBackdrop.classList.remove('open');
  }

  function handleHoldSubmit(e) {
    e.preventDefault();
    const id = DOM.holdTicketId.value;
    const inc = state.incidents.find(i => i.id === id);
    if (!inc) return;

    const reason = DOM.selectHoldReason.value;
    const notes = DOM.inputHoldNotes.value.trim();

    inc.status = 'ON_HOLD';
    inc.isPaused = true;
    inc.holdReason = reason;
    inc.holdNotes = notes;

    inc.timeline.unshift({
      time: 'Just now',
      user: 'Alex Rivera (SRE)',
      text: `Placed on hold: [${reason}]. Notes: ${notes}. SLA clock paused.`
    });

    closeHoldModal();
    renderTickets();
    if (state.selectedTicket && state.selectedTicket.id === id) {
      openTicketDrawer(id);
    }
    showToast(`⏸️ Incident ${id} placed on hold (${reason}). SLA paused.`, 'warning');
  }

  // =========================================================================
  // VIEW 6: CREATE TICKET MODAL WITH REAL-TIME AI ASSIST
  // =========================================================================


  // =========================================================================
  // INTERACTIVE 4-STEP WIZARD ENGINE (ZERO COGNITIVE OVERLOAD)
  // =========================================================================

  function switchWizardStep(stepNum) {
    state.wizardStep = stepNum;

    // 1. Update Stepper Tabs
    for (let i = 1; i <= 4; i++) {
      const tab = document.getElementById(`wizard-tab-${i}`);
      const conn = document.getElementById(`wizard-conn-${i}`);

      if (tab) {
        tab.classList.remove('active', 'completed');
        if (i < stepNum) {
          tab.classList.add('completed');
        } else if (i === stepNum) {
          tab.classList.add('active');
        }
      }

      if (conn) {
        if (i < stepNum) {
          conn.classList.add('active');
        } else {
          conn.classList.remove('active');
        }
      }
    }

    // 2. Update Counter Pill
    const counter = document.getElementById('wizard-step-counter');
    if (counter) counter.textContent = `Step ${stepNum} of 4`;

    // 3. Toggle Wizard Panels
    document.querySelectorAll('.wizard-panel').forEach(panel => {
      panel.style.display = 'none';
      panel.classList.remove('active');
    });

    const activePanel = document.getElementById(`wizard-panel-${stepNum}`);
    if (activePanel) {
      activePanel.style.display = 'block';
      activePanel.classList.add('active');
    }

    // Focus first input of panel
    if (stepNum === 1 && DOM.inputTicketTitle) DOM.inputTicketTitle.focus();
  }

  function openCreateModal(defaults = {}) {
    switchWizardStep(1);

    if (defaults.ci && DOM.selectTicketCi) DOM.selectTicketCi.value = defaults.ci;

    if (DOM.inputTicketTitle) DOM.inputTicketTitle.value = '';
    if (DOM.inputTicketDesc) DOM.inputTicketDesc.value = '';
    if (DOM.liveAiCopilotContent) {
      DOM.liveAiCopilotContent.innerHTML = `
        <div class="ai-empty-prompt">
          <div class="ai-pulsing-rings">
            <div class="ring-1"></div>
            <div class="ring-2"></div>
          </div>
          <p>AI Copilot actively analyzes the symptoms entered in Step 1 to predict root cause, blast radius risk, and recommended runbook steps.</p>
        </div>
      `;
    }

    populateClassificationDropdowns(
      DOM.selectTicketCategory,
      DOM.selectTicketSubcategory,
      DOM.selectTicketItem,
      defaults.category || 'Database & Storage',
      defaults.subcategory,
      defaults.item
    );

    if (DOM.selectTicketImpact) DOM.selectTicketImpact.value = defaults.impact || 'Enterprise';
    if (DOM.selectTicketUrgency) DOM.selectTicketUrgency.value = defaults.urgency || (defaults.priority === 'P1' ? 'Critical' : defaults.priority === 'P3' ? 'Medium' : 'High');

    setupPriorityMatrixCalculator(
      DOM.selectTicketImpact,
      DOM.selectTicketUrgency,
      DOM.createPriorityPreviewBadge,
      DOM.createPriorityCalcLabel,
      DOM.selectTicketPriority
    );

    if (defaults.category || defaults.ci) {
      applyBusinessRuleToCreateModal();
    }

    if (DOM.createModalBackdrop) DOM.createModalBackdrop.classList.add('open');
    if (DOM.inputTicketTitle) DOM.inputTicketTitle.focus();
  }

  function closeCreateModal() {
    if (DOM.createModalBackdrop) DOM.createModalBackdrop.classList.remove('open');
  }

  let aiDebounceTimer = null;
  function handleLiveAiAssist() {
    const title = DOM.inputTicketTitle.value.trim();
    const desc = DOM.inputTicketDesc.value.trim();
    const combined = `${title} ${desc}`.toLowerCase();

    if (combined.length < 5) return;

    if (DOM.aiTypingStatus) DOM.aiTypingStatus.style.display = 'inline-flex';

    clearTimeout(aiDebounceTimer);
    aiDebounceTimer = setTimeout(() => {
      if (DOM.aiTypingStatus) DOM.aiTypingStatus.style.display = 'none';

      let suggestedPriority = 'P3';
      let suggestedCi = 'CI-K8S-006';
      let category = 'Application Infrastructure';
      let hypothesis = 'Container scheduling or network packet delay.';

      if (combined.includes('postgres') || combined.includes('sql') || combined.includes('lock') || combined.includes('db')) {
        suggestedPriority = 'P1';
        suggestedCi = 'CI-DB-001';
        category = 'Database Locks & Saturation';
        hypothesis = 'Database transaction deadlock or connection limit starvation.';
      } else if (combined.includes('stripe') || combined.includes('pay') || combined.includes('checkout') || combined.includes('billing')) {
        suggestedPriority = 'P1';
        suggestedCi = 'CI-PAY-003';
        category = 'Payment Ingress & Webhook Timeout';
        hypothesis = 'Payment provider webhook response timeout > 3000ms threshold.';
      } else if (combined.includes('redis') || combined.includes('oom') || combined.includes('cache') || combined.includes('memory')) {
        suggestedPriority = 'P2';
        suggestedCi = 'CI-CACHE-002';
        category = 'Cache Cluster Memory Pressure';
        hypothesis = 'In-memory keyspace exhaustion causing volatile key evictions.';
      } else if (combined.includes('cert') || combined.includes('tls') || combined.includes('ssl') || combined.includes('kong')) {
        suggestedPriority = 'P2';
        suggestedCi = 'CI-INGRESS-005';
        category = 'API Gateway Ingress & TLS Certificates';
        hypothesis = 'ACME DNS-01 certificate challenge validation failure.';
      }

      DOM.liveAiCopilotContent.innerHTML = `
        <div class="ai-insights-active-card">
          <div class="ai-insight-item">
            <span class="insight-label">AI Suggested Category</span>
            <span class="insight-content text-indigo">${category}</span>
          </div>

          <div class="ai-insight-item">
            <span class="insight-label">Severity Recommendation</span>
            <span class="insight-content font-bold ${suggestedPriority === 'P1' ? 'text-rose' : 'text-amber'}">
              ${suggestedPriority} Severity (Calculated impact probability: 96%)
            </span>
          </div>

          <div class="ai-insight-item">
            <span class="insight-label">Root Cause Hypothesis</span>
            <span class="insight-content text-secondary text-sm">${hypothesis}</span>
          </div>

          <div class="ai-insight-item">
            <span class="insight-label">Similar Past Incidents</span>
            <span class="insight-content font-mono text-sm text-blue">INC-8104: Aurora PostgreSQL lock exhaustion (Resolved)</span>
          </div>

          <button type="button" class="btn btn-sm btn-zen-primary w-full mt-2" id="btn-accept-ai-suggestions">
            ✦ Apply AI Suggestions to Form
          </button>
        </div>
      `;

      const acceptBtn = document.getElementById('btn-accept-ai-suggestions');
      if (acceptBtn) {
        acceptBtn.addEventListener('click', () => {
          DOM.selectTicketCi.value = suggestedCi;
          if (suggestedPriority === 'P1') {
            DOM.selectTicketImpact.value = 'Enterprise';
            DOM.selectTicketUrgency.value = 'Critical';
          } else if (suggestedPriority === 'P2') {
            DOM.selectTicketImpact.value = 'Department';
            DOM.selectTicketUrgency.value = 'High';
          } else {
            DOM.selectTicketImpact.value = 'Department';
            DOM.selectTicketUrgency.value = 'Medium';
          }
          if (category.includes('Database')) {
            populateClassificationDropdowns(DOM.selectTicketCategory, DOM.selectTicketSubcategory, DOM.selectTicketItem, 'Database & Storage', 'PostgreSQL Aurora', 'Deadlock / Lock Contention');
          } else if (category.includes('Payment')) {
            populateClassificationDropdowns(DOM.selectTicketCategory, DOM.selectTicketSubcategory, DOM.selectTicketItem, 'Software & Applications', 'Payment Gateway', 'Webhook 504 Timeout');
          } else if (category.includes('Cache')) {
            populateClassificationDropdowns(DOM.selectTicketCategory, DOM.selectTicketSubcategory, DOM.selectTicketItem, 'Database & Storage', 'Redis Cache', 'Memory Pressure / OOM Eviction');
          } else if (category.includes('Gateway')) {
            populateClassificationDropdowns(DOM.selectTicketCategory, DOM.selectTicketSubcategory, DOM.selectTicketItem, 'Cloud & Infrastructure', 'API Gateway (Kong)', 'TLS Certificate Auto-Renewal Failure');
          }
          setupPriorityMatrixCalculator(DOM.selectTicketImpact, DOM.selectTicketUrgency, DOM.createPriorityPreviewBadge, DOM.createPriorityCalcLabel, DOM.selectTicketPriority);
          showToast('Applied AI suggested priority, CI & classification to form.', 'info');
        });
      }
    }, 350);
  }

  function handleCreateTicketSubmit(e) {
    e.preventDefault();

    const title = DOM.inputTicketTitle.value.trim();
    const desc = DOM.inputTicketDesc.value.trim();
    const ci = DOM.selectTicketCi.value;
    const team = DOM.selectTicketTeam.value;
    const category = DOM.selectTicketCategory.value;
    const subcategory = DOM.selectTicketSubcategory.value;
    const item = DOM.selectTicketItem.value;
    const impact = DOM.selectTicketImpact.value;
    const urgency = DOM.selectTicketUrgency.value;
    const priority = calculatePriority(impact, urgency);

    if (!title || !desc) return;

    const newId = `INC-${Math.floor(1000 + Math.random() * 9000)}`;
    const ciObj = state.cmdbNodes.find(n => n.id === ci);

    const newTicket = {
      id: newId,
      title: title,
      description: desc,
      ci: ci,
      ciName: ciObj ? ciObj.name : ci,
      category: category,
      subcategory: subcategory,
      item: item,
      impact: impact,
      urgency: urgency,
      priority: priority,
      status: 'NEW',
      team: team,
      caller: 'alex.rivera@opennow.io',
      createdAt: 'Just now',
      slaSecondsRemaining: priority === 'P1' ? 1800 : priority === 'P2' ? 7200 : 14400,
      slaInitialSeconds: 14400,
      isPaused: false,
      holdReason: '',
      holdNotes: '',
      totalPausedSeconds: 0,
      aiTriageDone: true,
      aiConfidence: '97.2%',
      worklogs: [],
      subtasks: [
        {
          id: `SUB-${Date.now()}`,
          title: `Initial SRE triage and telemetry verification for ${ci}`,
          assignee: 'Alex Rivera (SRE)',
          completed: false,
          completedAt: null
        }
      ],
      timeline: [
        { time: 'Just now', user: 'Alex Rivera (SRE)', text: `Created incident. Classification: ${category} ➔ ${subcategory} ➔ ${item}. Impact: ${impact}, Urgency: ${urgency} (${priority}).` },
        { time: 'Just now', user: 'Sentinel-AI', text: 'Auto-assigned incident and synchronized with CMDB topology.', isAi: true }
      ]
    };

    if (priority === 'P1' && ciObj) {
      ciObj.health = 'critical';
      ciObj.activeIncidents.push(newId);
    }

    state.incidents.unshift(newTicket);
    closeCreateModal();
    renderTickets();
    setupCmdbGraph();

    showToast(`🚀 Incident ${newId} dispatched successfully!`, 'success');
  }

  // =========================================================================
  // VIEW 6: AI OPS CENTER & STREAM
  // =========================================================================

  function renderAiEvents() {
    if (!DOM.aiEventsStreamList) return;

    DOM.aiEventsStreamList.innerHTML = state.aiEvents.map(e => `
      <div class="event-row">
        <span class="event-time">${e.time}</span>
        <span class="event-agent-tag">[${escapeHtml(e.agent)}]</span>
        <span class="event-msg">${escapeHtml(e.msg)}</span>
      </div>
    `).join('');
  }

  // =========================================================================
  // COMMAND PALETTE (CMD+K / CTRL+K MODAL)
  // =========================================================================

  function openCommandPalette() {
    DOM.cmdPaletteInput.value = '';
    renderCommandResults('');
    DOM.cmdPaletteModal.classList.add('open');
    DOM.cmdPaletteInput.focus();
  }

  function closeCommandPalette() {
    DOM.cmdPaletteModal.classList.remove('open');
  }

  function renderCommandResults(query) {
    const q = query.toLowerCase().trim();
    let html = '';

    const actions = [
      { id: 'act-new', title: 'File New Production Incident', sub: 'Open AI-assisted triage modal', run: () => openCreateModal() },
      { id: 'act-zen', title: 'Toggle Zen Focus Mode', sub: 'Minimize chrome for high tranquil focus', run: () => toggleZenMode() },
      { id: 'act-chaos', title: 'Simulate Chaos Incident', sub: 'Inject simulated production outage', run: () => triggerChaosSimulation() },
      { id: 'act-blast', title: 'Simulate CMDB Blast Radius', sub: 'Visualize cascading downstream outage', run: () => { switchView('cmdb-topology'); toggleBlastRadiusSimulation(); } },
      { id: 'act-mig-snow', title: 'Load ServiceNow Sample', sub: 'Instant 1-click test migration', run: () => { switchView('migration-studio'); handlePlatformSampleLoad('servicenow'); } },
      { id: 'act-mig-jira', title: 'Load Jira Service Management Sample', sub: 'Instant 1-click test migration', run: () => { switchView('migration-studio'); handlePlatformSampleLoad('jira'); } }
    ];

    const filteredActions = actions.filter(a => a.title.toLowerCase().includes(q) || a.sub.toLowerCase().includes(q));
    if (filteredActions.length > 0) {
      html += `<div class="cmd-category-title">Quick Actions</div>`;
      filteredActions.forEach(a => {
        html += `
          <div class="cmd-item" data-action-id="${a.id}">
            <div class="cmd-item-left">
              <span class="cmd-item-title">${escapeHtml(a.title)}</span>
              <span class="cmd-item-sub">${escapeHtml(a.sub)}</span>
            </div>
            <kbd class="key-badge">Action</kbd>
          </div>
        `;
      });
    }

    const filteredTickets = state.incidents.filter(i => i.id.toLowerCase().includes(q) || i.title.toLowerCase().includes(q));
    if (filteredTickets.length > 0) {
      html += `<div class="cmd-category-title">Incidents (${filteredTickets.length})</div>`;
      filteredTickets.slice(0, 5).forEach(t => {
        html += `
          <div class="cmd-item" data-ticket-id="${t.id}">
            <div class="cmd-item-left">
              <span class="priority-pill pill-${t.priority.toLowerCase()}">${t.priority}</span>
              <span class="cmd-item-title font-mono">${t.id}</span>
              <span class="cmd-item-sub">${escapeHtml(t.title)}</span>
            </div>
            <span class="badge-tag">${formatStatusLabel(t.status)}</span>
          </div>
        `;
      });
    }

    const filteredNodes = state.cmdbNodes.filter(n => n.id.toLowerCase().includes(q) || n.name.toLowerCase().includes(q));
    if (filteredNodes.length > 0) {
      html += `<div class="cmd-category-title">CMDB Topology Items</div>`;
      filteredNodes.forEach(n => {
        html += `
          <div class="cmd-item" data-node-id="${n.id}">
            <div class="cmd-item-left">
              <span class="cmd-item-title font-mono">${n.id}</span>
              <span class="cmd-item-sub">${escapeHtml(n.name)} (${n.tier})</span>
            </div>
            <span class="badge-tag ${n.health === 'critical' ? 'text-rose' : 'text-emerald'}">${n.health.toUpperCase()}</span>
          </div>
        `;
      });
    }

    DOM.cmdResultsContainer.innerHTML = html || `<div style="padding:20px;text-align:center;color:#64748b;">No results matching "${escapeHtml(q)}"</div>`;

    DOM.cmdResultsContainer.querySelectorAll('.cmd-item').forEach(item => {
      item.addEventListener('click', () => {
        closeCommandPalette();
        const actionId = item.getAttribute('data-action-id');
        const ticketId = item.getAttribute('data-ticket-id');
        const nodeId = item.getAttribute('data-node-id');

        if (actionId) {
          const act = actions.find(a => a.id === actionId);
          if (act) act.run();
        } else if (ticketId) {
          openTicketDrawer(ticketId);
        } else if (nodeId) {
          switchView('cmdb-topology');
          openCmdbInspector(nodeId);
        }
      });
    });
  }

  // =========================================================================
  // CHAOS SIMULATOR
  // =========================================================================

  function triggerChaosSimulation() {
    const chaosScenarios = [
      {
        title: 'Kafka Cluster Partition 03 Disk OOM Crash',
        ci: 'CI-KAFKA-007',
        priority: 'P1',
        team: 'Payment-Platform',
        desc: 'Unprecedented volume surge on topic orders.finalized led to broker node disk exhaustion and quorum loss.'
      },
      {
        title: 'Kong Ingress Core Dump on Memory Leak',
        ci: 'CI-INGRESS-005',
        priority: 'P1',
        team: 'Cloud-Infra',
        desc: 'Envoy worker thread segfaulted under high concurrent SSL handshake volume.'
      }
    ];

    const scenario = chaosScenarios[Math.floor(Math.random() * chaosScenarios.length)];
    const newId = `INC-${Math.floor(9200 + Math.random() * 500)}`;

    const node = state.cmdbNodes.find(n => n.id === scenario.ci);
    if (node) {
      node.health = 'critical';
      node.cpu = 99;
      node.latency = 2200;
      node.activeIncidents.push(newId);
    }

    state.incidents.unshift({
      id: newId,
      title: scenario.title,
      description: scenario.desc,
      ci: scenario.ci,
      ciName: node ? node.name : scenario.ci,
      priority: scenario.priority,
      status: 'NEW',
      team: scenario.team,
      caller: 'chaos-monkey@opennow.io',
      createdAt: 'Just now',
      slaSecondsRemaining: 1800,
      slaInitialSeconds: 3600,
      aiTriageDone: true,
      aiConfidence: '99.8%',
      timeline: [
        { time: 'Just now', user: 'Chaos Simulator', text: 'Injected artificial production fault.', isAi: true }
      ]
    });

    state.aiEvents.unshift({
      time: 'Just now',
      agent: 'Sentinel-Triage AI',
      msg: `DETECTED CHAOS CRASH on ${scenario.ci}: Dispatched ${newId} with P1 Critical priority.`
    });

    renderTickets();
    setupCmdbGraph();
    renderAiEvents();

    showToast(`⚡ CHAOS INJECTED: ${newId} (${scenario.title}) created!`, 'error');
  }

  // =========================================================================
  // VIEW 6: ENTERPRISE SETUP & MASTER DATA CONFIGURATION CENTER
  // =========================================================================

  const DEFAULT_INDUSTRY_BLUEPRINTS = [
    {
      id: 'fintech',
      name: 'FinTech, Banking & Capital Markets',
      icon: '💳',
      theme: 'bp-theme-fintech',
      sub_industries: ['Payment Processing & Acquiring', 'Neo-Banking & Core Ledgers', 'Algorithmic Trading & WealthTech', 'Lending & Mortgage Underwriting'],
      primary_offering: 'High-Throughput Payment Authorization Rails & Settlement Ledger',
      tech_stack: 'Kafka, PostgreSQL Aurora, Redis, HSM, AWS GovCloud, Cloudflare Anycast, Go',
      compliance_standard: 'PCI-DSS Level 1 / SOX 404 / GLBA',
      downtime_cost_per_minute: 18500,
      sla_p1_resolve_hours: 0.5,
      sla_p1_response_mins: 5,
      key_cis: ['Core Banking Ledger', 'Card Ingress 3DS Gateway', 'Thales Luna HSM Vault', 'Kafka Payment Event Bus']
    },
    {
      id: 'healthcare',
      name: 'Healthcare & Life Sciences',
      icon: '🏥',
      theme: 'bp-theme-healthcare',
      sub_industries: ['Hospital Electronic Health Records (EHR)', 'IoMT Bedside Telemetry & ICU', 'PACS / DICOM Diagnostic Imaging', 'Telemedicine & Clinical Operations'],
      primary_offering: 'Clinical Care EHR Platform & IoMT Critical Care Telemetry',
      tech_stack: 'HL7 / FHIR v4, DICOM PACS, Epic Interconnect, PostgreSQL, MQTT, Kubernetes',
      compliance_standard: 'HIPAA / HITECH / FDA 21 CFR Part 11',
      downtime_cost_per_minute: 24000,
      sla_p1_resolve_hours: 0.25,
      sla_p1_response_mins: 3,
      key_cis: ['Epic FHIR Integration Gateway', 'DICOM PACS Imaging Store', 'Bedside Vitals IoMT Broker', 'Pharmacy Dispense Engine']
    },
    {
      id: 'retail',
      name: 'E-Commerce, Omnichannel Retail & Logistics',
      icon: '🛒',
      theme: 'bp-theme-retail',
      sub_industries: ['Omnichannel Direct-to-Consumer (D2C)', 'Warehouse Management & Automated WMS', 'Point-of-Sale (POS) & Store Systems', 'Order Fulfillment & Global Shipping'],
      primary_offering: 'Global Multi-Region E-Commerce Storefront & Real-Time Checkout',
      tech_stack: 'Next.js, Stripe, Elasticsearch, Redis Inventory Cluster, Kafka, Kubernetes',
      compliance_standard: 'PCI-DSS Level 1 / SOC2 Type II',
      downtime_cost_per_minute: 14000,
      sla_p1_resolve_hours: 1.0,
      sla_p1_response_mins: 10,
      key_cis: ['Cart & Checkout API', 'Real-Time Inventory Lock Engine', 'Elasticsearch Catalog Cluster', 'Stripe Payment Ingress']
    },
    {
      id: 'saas_ai',
      name: 'Cloud Tech, Developer SaaS & Autonomous AI',
      icon: '⚡',
      theme: 'bp-theme-saas_ai',
      sub_industries: ['LLM Inference & Autonomous Agent Platform', 'Vector Search & Embeddings Infrastructure', 'DevSecOps & Cloud Platform (PaaS)', 'API Management & Developer Ecosystem'],
      primary_offering: 'Low-Latency LLM Inference API & Agent Orchestration Mesh',
      tech_stack: 'NVIDIA H100 GPUs, Qdrant Vector DB, vLLM, Envoy Ingress, Kubernetes, Prometheus',
      compliance_standard: 'SOC2 Type II / ISO 27001 / FedRAMP',
      downtime_cost_per_minute: 11000,
      sla_p1_resolve_hours: 0.75,
      sla_p1_response_mins: 8,
      key_cis: ['NVIDIA H100 GPU Cluster', 'Qdrant Vector DB Cluster', 'vLLM Inference Gateway', 'Envoy Service Mesh Ingress']
    },
    {
      id: 'manufacturing',
      name: 'Manufacturing & Industrial IoT',
      icon: '🏭',
      theme: 'bp-theme-manufacturing',
      sub_industries: ['Automotive & Aerospace Robotics', 'SCADA & Industrial Control Systems', 'MES Plant Floor Execution', 'Supply Chain Telemetry & Predictive Maintenance'],
      primary_offering: 'Automated Robotics Assembly Line & SCADA Telemetry Controller',
      tech_stack: 'Siemens S7 PLCs, OPC-UA, MQTT Sparkplug B, Historian InfluxDB, Node-RED',
      compliance_standard: 'ISA-95 / IEC 62443 / ISO 9001',
      downtime_cost_per_minute: 26000,
      sla_p1_resolve_hours: 0.33,
      sla_p1_response_mins: 5,
      key_cis: ['SCADA Supervisory System', 'Siemens S7 Assembly Line PLC', 'MQTT Sparkplug Edge Broker', 'Historian InfluxDB Time-Series']
    },
    {
      id: 'telecom',
      name: 'Telecommunications & 5G Carrier Operations',
      icon: '📡',
      theme: 'bp-theme-telecom',
      sub_industries: ['5G Standalone (SA) Mobile Packet Core', 'Fiber Broadband & ISP Transport Network', 'VoLTE / VoNR & E911 Emergency Services', 'BGP Carrier Peering & Edge CDN'],
      primary_offering: '5G Standalone Packet Core & Tier-1 BGP Border Peering',
      tech_stack: '5G SA UPF/AMF Core, Cisco 8000 BGP, Open5GS, Kamailio SIP, eBPF, PTP IEEE 1588',
      compliance_standard: 'FCC Title 47 / 3GPP Rel-16 / ETSI NFV',
      downtime_cost_per_minute: 21000,
      sla_p1_resolve_hours: 0.25,
      sla_p1_response_mins: 3,
      key_cis: ['5G Standalone UPF Packet Core', 'Cisco 8000 Tier-1 BGP Border', 'VoLTE E911 Emergency Core', 'Kamailio SIP Proxy Cluster']
    }
  ];

  async function fetchCompanyDna() {
    try {
      const [curRes, bpRes] = await Promise.all([
        fetch('/api/v2/industry/current'),
        fetch('/api/v2/industry/blueprints')
      ]);
      if (curRes.ok) {
        const curData = await curRes.json();
        if (curData.status === 'success' && curData.dna) {
          state.companyDna = curData.dna;
          state.industry = curData.dna.industry_id;
          updateHeaderIndustryPill();
        }
      }
      if (bpRes.ok) {
        const bpData = await bpRes.json();
        if (bpData.status === 'success' && bpData.blueprints) {
          state.industryBlueprints = bpData.blueprints;
        }
      }
    } catch (e) {
      console.warn('Company DNA API unavailable; using defaults.', e);
    }
  }

  function updateHeaderIndustryPill() {
    const dna = state.companyDna;
    if (!dna) return;
    const icons = {
      fintech: '💳',
      healthcare: '🏥',
      retail: '🛒',
      saas_ai: '⚡',
      manufacturing: '🏭',
      telecom: '📡'
    };
    const iconEl = document.getElementById('header-industry-icon');
    const nameEl = document.getElementById('header-industry-name');
    const compEl = document.getElementById('header-industry-compliance');
    const badgeEl = document.getElementById('badge-current-industry');

    if (iconEl) iconEl.textContent = icons[dna.industry_id] || '🏢';
    if (nameEl) {
      const shortNames = {
        fintech: 'FinTech Banking',
        healthcare: 'Healthcare EHR',
        retail: 'Retail E-Com',
        saas_ai: 'Cloud SaaS AI',
        manufacturing: 'Manufacturing',
        telecom: 'Telecom 5G'
      };
      nameEl.textContent = shortNames[dna.industry_id] || dna.industry_name || 'Enterprise';
    }
    if (compEl) {
      const compShort = (dna.compliance_standard || 'PCI-DSS').split('/')[0].split('•')[0].trim();
      compEl.textContent = compShort;
    }
    if (badgeEl) {
      badgeEl.textContent = dna.industry_id.toUpperCase();
    }
  }

  async function applyIndustryBlueprint(industryId, customPayload = null) {
    try {
      showToast(`Recalibrating OpenNow to ${industryId.toUpperCase()}...`, 'info');
      const payload = customPayload || { industry_id: industryId };
      const res = await fetch('/api/v2/industry/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        state.companyDna = data.dna;
        state.industry = data.dna.industry_id;
        if (data.taxonomies) {
          state.taxonomy = data.taxonomies;
        }
        if (data.blueprint && data.blueprint.cmdb_nodes) {
          state.cmdbNodes = data.blueprint.cmdb_nodes.map(node => ({
            id: node.id,
            name: node.name,
            type: node.ci_type || node.type,
            env: 'Production',
            health: node.health_status || node.health || 'healthy',
            tier: node.tier || 'Tier 1',
            ip: node.ip_address || '10.0.1.10',
            team: node.owner_team || node.provider || 'Core-Ops',
            upstream: node.upstream_deps || [],
            downstream: node.downstream_deps || [],
            incidents: 0
          }));
        }
        updateHeaderIndustryPill();
        renderSetupCenter('dna');
        if (state.currentView === 'cmdb-topology') {
          setupCmdbGraph();
        }
        showToast(`🏢 OpenNow successfully calibrated to ${data.dna.industry_name}!`, 'success');
      } else {
        showToast(data.detail || 'Failed to apply blueprint', 'error');
      }
    } catch (e) {
      showToast(`Error applying blueprint: ${e.message}`, 'error');
    }
  }

  // --- Module 0: Company DNA & Adaptive Industry Blueprints ---
  function renderModuleCompanyDna() {
    const dna = state.companyDna || {
      industry_id: 'fintech',
      industry_name: 'FinTech, Banking & Capital Markets',
      sub_industry: 'Payment Processing & Acquiring',
      primary_offering: 'High-Throughput Payment Authorization Rails & Settlement Ledger',
      tech_stack: 'Kafka, PostgreSQL Aurora, Redis, HSM, AWS GovCloud, Cloudflare Anycast, Go',
      compliance_standard: 'PCI-DSS Level 1 / SOX 404 / GLBA',
      downtime_cost_per_minute: 18500
    };

    const blueprints = state.industryBlueprints && state.industryBlueprints.length > 0 ? state.industryBlueprints : DEFAULT_INDUSTRY_BLUEPRINTS;
    const costPerMin = parseFloat(dna.downtime_cost_per_minute) || 18500;
    const costPerHour = costPerMin * 60;
    const costPerDay = costPerMin * 1440;

    return `
      <div class="dna-workspace-container">
        <!-- Active DNA Hero Strip -->
        <div class="dna-hero-card">
          <div class="dna-hero-left">
            <div class="dna-hero-pill-badge">
              <span class="live-pulse-dot" style="background:#2563eb;"></span>
              <span>ACTIVE COMPANY DNA ARCHETYPE</span>
            </div>
            <h3 class="dna-hero-title">${escapeHtml(dna.industry_name)}</h3>
            <p class="dna-hero-desc">
              <strong>Offering:</strong> ${escapeHtml(dna.primary_offering || 'Enterprise Mission-Critical Services')} • 
              <strong>Sub-Industry:</strong> ${escapeHtml(dna.sub_industry || 'Tier 1 Operations')} • 
              <strong>Stack:</strong> ${escapeHtml(dna.tech_stack || 'Distributed Microservices, Multi-AZ Database, Cloud Mesh')}
            </p>
          </div>
          <div class="dna-hero-metrics">
            <div class="dna-metric-box metric-alert">
              <span class="dna-metric-val font-mono">$${costPerMin.toLocaleString()}</span>
              <span class="dna-metric-sub">Downtime Cost / Min</span>
            </div>
            <div class="dna-metric-box">
              <span class="dna-metric-val font-mono">$${Math.round(costPerHour / 1000)}k</span>
              <span class="dna-metric-sub">Hourly Outage Risk</span>
            </div>
            <div class="dna-metric-box">
              <span class="dna-metric-val" style="font-size:14px; font-weight:800; color:#4f46e5;">${escapeHtml((dna.compliance_standard || 'PCI-DSS').split('/')[0].trim())}</span>
              <span class="dna-metric-sub">Primary Standard</span>
            </div>
          </div>
        </div>

        <!-- Section: 6 Enterprise Blueprints Catalog -->
        <div>
          <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:14px;">
            <div>
              <h4 style="font-size:16px; font-weight:800; color:#0f172a;">Adaptive Enterprise Blueprints</h4>
              <p style="font-size:12.5px; color:#64748b; margin-top:2px;">Switching blueprints automatically reconfigures 3-tier taxonomies, CMDB topology nodes, SLA countdown timers, and financial downtime risk across OpenNow.</p>
            </div>
            <span class="badge-tag tag-aurora">6 Validated Archetypes</span>
          </div>

          <div class="dna-blueprints-grid">
            ${blueprints.map(bp => {
              const isActive = dna.industry_id === bp.id;
              const bpCost = parseFloat(bp.downtime_cost_per_minute) || 15000;
              const themeClass = bp.theme || `bp-theme-${bp.id}`;
              const subTags = Array.isArray(bp.sub_industries) ? bp.sub_industries.slice(0, 3) : ['Core Operations', 'Edge Rails'];
              const keyCis = bp.key_cis || (bp.cmdb_nodes ? bp.cmdb_nodes.slice(0, 3).map(n => n.name) : ['Core Service', 'Database Gateway']);

              return `
                <div class="blueprint-card ${themeClass} ${isActive ? 'active' : ''}" data-bp-id="${bp.id}">
                  <div>
                    <div class="bp-header">
                      <div class="bp-icon-wrap">${bp.icon || '🏢'}</div>
                      <div class="bp-title-wrap">
                        <h4 class="bp-name">${escapeHtml(bp.name)}</h4>
                        <span class="bp-compliance-badge">${escapeHtml(bp.compliance_standard || 'Enterprise Governance')}</span>
                      </div>
                      ${isActive ? '<span class="bp-active-indicator"><span class="bp-active-pulse"></span>Active</span>' : ''}
                    </div>

                    <p class="bp-desc">${escapeHtml(bp.primary_offering || 'Enterprise service platform architecture with mission-critical SLA models.')}</p>

                    <div class="bp-specs-list font-mono">
                      <div class="bp-spec-row">
                        <span class="bp-spec-key">Downtime Risk:</span>
                        <span class="bp-spec-val text-rose font-bold">$${bpCost.toLocaleString()}/min</span>
                      </div>
                      <div class="bp-spec-row">
                        <span class="bp-spec-key">P1 Target SLA:</span>
                        <span class="bp-spec-val text-emerald font-bold">${bp.sla_p1_resolve_hours ? (bp.sla_p1_resolve_hours * 60) + 'm' : '30m'} resolve (${bp.sla_p1_response_mins || 5}m ack)</span>
                      </div>
                      <div class="bp-spec-row">
                        <span class="bp-spec-key">Core CMDB Nodes:</span>
                        <span class="bp-spec-val" title="${keyCis.join(', ')}">${escapeHtml(keyCis.slice(0, 2).join(' • '))}</span>
                      </div>
                    </div>

                    <div class="bp-tags-wrap">
                      ${subTags.map(st => `<span class="bp-tag">${escapeHtml(st)}</span>`).join('')}
                    </div>
                  </div>

                  <div class="bp-footer">
                    <button class="btn-apply-blueprint" data-bp-id="${bp.id}">
                      ${isActive ? '✓ Blueprint Currently Active' : '⚡ 1-Click Apply Blueprint'}
                    </button>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Section: Company DNA Calibration & Financial Risk Engine -->
        <div class="dna-tailoring-panel">
          <div class="dna-panel-header">
            <h4 class="dna-panel-title">Custom Company DNA Calibration &amp; Exposure Engine</h4>
            <p class="dna-panel-sub">Fine-tune your company's sub-industry, offering title, core infrastructure stack, and financial downtime rate. Live calculation updates business interruption exposure in real time.</p>
          </div>

          <form id="form-dna-recalibrate" class="dna-form-grid">
            <div class="form-group">
              <label class="text-xs text-muted font-bold">Industry Archetype</label>
              <select id="dna-select-industry" class="zen-select w-full" style="height:36px;">
                ${blueprints.map(bp => `<option value="${bp.id}" ${bp.id === dna.industry_id ? 'selected' : ''}>${bp.icon || '🏢'} ${escapeHtml(bp.name)}</option>`).join('')}
              </select>
            </div>

            <div class="form-group">
              <label class="text-xs text-muted font-bold">Sub-Industry / Domain Specialty</label>
              <input type="text" id="dna-input-subindustry" class="zen-form-control" value="${escapeHtml(dna.sub_industry || '')}" placeholder="e.g. Payment Processing, Card Ingress, Neonatal Telemetry" style="height:36px;">
            </div>

            <div class="form-group dna-form-full">
              <label class="text-xs text-muted font-bold">Primary Company Offering / Flagship Service</label>
              <input type="text" id="dna-input-offering" class="zen-form-control" value="${escapeHtml(dna.primary_offering || '')}" placeholder="e.g. OpenPay Global Clearing & Settlement Rails" style="height:36px;">
            </div>

            <div class="form-group dna-form-full">
              <label class="text-xs text-muted font-bold">Core Technology Stack</label>
              <input type="text" id="dna-input-techstack" class="zen-form-control font-mono" value="${escapeHtml(dna.tech_stack || '')}" placeholder="e.g. Kafka, PostgreSQL Aurora, Redis, Kubernetes, HSMs, AWS GovCloud" style="height:36px;">
            </div>

            <div class="form-group">
              <label class="text-xs text-muted font-bold">Compliance &amp; Regulatory Standard</label>
              <input type="text" id="dna-input-compliance" class="zen-form-control" value="${escapeHtml(dna.compliance_standard || 'PCI-DSS Level 1 / SOC2 Type II')}" placeholder="e.g. PCI-DSS Level 1, HIPAA, SOC2 Type II, ISO 27001" style="height:36px;">
            </div>

            <div class="form-group">
              <label class="text-xs text-muted font-bold">Financial Downtime Cost Rate ($ / Minute)</label>
              <div style="display:flex; align-items:center; gap:8px;">
                <input type="number" id="dna-input-cost" class="zen-form-control font-mono" value="${costPerMin}" min="100" max="1000000" step="500" style="height:36px;">
                <span class="text-xs text-muted">USD / min</span>
              </div>
            </div>

            <!-- Dynamic Outage Exposure Calculator Callout -->
            <div class="dna-downtime-calculator-card">
              <div class="calc-left">
                <h4>⚠️ Calculated Business Interruption Exposure</h4>
                <p>Real-time ITIL v4 downtime financial risk projection modeled against current SLA targets.</p>
              </div>
              <div class="calc-rates font-mono">
                <div class="calc-rate-box">
                  <span class="calc-rate-val" id="calc-exp-min">$${costPerMin.toLocaleString()}</span>
                  <span class="calc-rate-label">Per Minute</span>
                </div>
                <div class="calc-rate-box">
                  <span class="calc-rate-val" id="calc-exp-hour">$${costPerHour.toLocaleString()}</span>
                  <span class="calc-rate-label">1-Hour Outage</span>
                </div>
                <div class="calc-rate-box">
                  <span class="calc-rate-val" id="calc-exp-day">$${costPerDay.toLocaleString()}</span>
                  <span class="calc-rate-label">24-Hour Outage</span>
                </div>
              </div>
            </div>

            <div class="dna-form-full mt-2" style="display:flex; justify-content:flex-end;">
              <button type="submit" class="btn btn-zen-primary" id="btn-save-dna-custom" style="padding:10px 22px; font-weight:800;">
                <span>🚀 Save DNA &amp; Recalibrate OpenNow</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  function bindModuleCompanyDnaEvents() {
    // 1-Click apply buttons on blueprint cards
    document.querySelectorAll('.btn-apply-blueprint').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const bpId = btn.getAttribute('data-bp-id');
        if (bpId) {
          applyIndustryBlueprint(bpId);
        }
      });
    });

    document.querySelectorAll('.blueprint-card').forEach(card => {
      card.addEventListener('click', () => {
        const bpId = card.getAttribute('data-bp-id');
        if (bpId && state.companyDna?.industry_id !== bpId) {
          applyIndustryBlueprint(bpId);
        }
      });
    });

    // Dynamic cost calculator input listener
    const costInput = document.getElementById('dna-input-cost');
    if (costInput) {
      costInput.addEventListener('input', () => {
        const val = parseFloat(costInput.value) || 0;
        const hr = val * 60;
        const dy = val * 1440;
        const elMin = document.getElementById('calc-exp-min');
        const elHr = document.getElementById('calc-exp-hour');
        const elDy = document.getElementById('calc-exp-day');
        if (elMin) elMin.textContent = `$${val.toLocaleString()}`;
        if (elHr) elHr.textContent = `$${hr.toLocaleString()}`;
        if (elDy) elDy.textContent = `$${dy.toLocaleString()}`;
      });
    }

    // Auto-fill sub-industry when archetype changes in dropdown
    const indSelect = document.getElementById('dna-select-industry');
    if (indSelect) {
      indSelect.addEventListener('change', () => {
        const bpId = indSelect.value;
        const blueprints = state.industryBlueprints && state.industryBlueprints.length > 0 ? state.industryBlueprints : DEFAULT_INDUSTRY_BLUEPRINTS;
        const bp = blueprints.find(b => b.id === bpId);
        if (bp) {
          const subInput = document.getElementById('dna-input-subindustry');
          const offInput = document.getElementById('dna-input-offering');
          const techInput = document.getElementById('dna-input-techstack');
          const compInput = document.getElementById('dna-input-compliance');
          const cInput = document.getElementById('dna-input-cost');
          if (subInput && bp.sub_industries && bp.sub_industries.length) subInput.value = bp.sub_industries[0];
          if (offInput) offInput.value = bp.primary_offering || '';
          if (techInput) techInput.value = bp.tech_stack || '';
          if (compInput) compInput.value = bp.compliance_standard || '';
          if (cInput) {
            cInput.value = bp.downtime_cost_per_minute || 15000;
            cInput.dispatchEvent(new Event('input'));
          }
        }
      });
    }

    // Custom DNA form submission
    const formDna = document.getElementById('form-dna-recalibrate');
    if (formDna) {
      formDna.addEventListener('submit', (e) => {
        e.preventDefault();
        const indId = document.getElementById('dna-select-industry')?.value || 'fintech';
        const sub = document.getElementById('dna-input-subindustry')?.value || '';
        const off = document.getElementById('dna-input-offering')?.value || '';
        const tech = document.getElementById('dna-input-techstack')?.value || '';
        const comp = document.getElementById('dna-input-compliance')?.value || '';
        const cost = parseFloat(document.getElementById('dna-input-cost')?.value) || 18500;

        applyIndustryBlueprint(indId, {
          industry_id: indId,
          sub_industry: sub,
          primary_offering: off,
          tech_stack: tech,
          compliance_standard: comp,
          downtime_cost_per_minute: cost
        });
      });
    }
  }

  function initSetupCenter() {
    DOM.setupNavTabs = document.querySelectorAll('.setup-vertical-tab');
    DOM.setupNavTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const mod = tab.getAttribute('data-setup-tab');
        state.activeSetupModule = mod;
        renderSetupCenter(mod);
      });
    });

    renderSetupCenter(state.activeSetupModule || 'dna');
  }

  function renderSetupCenter(module = state.activeSetupModule || 'dna') {
    state.activeSetupModule = module;

    // Update active tab styles
    const navTabs = document.querySelectorAll('.setup-vertical-tab');
    navTabs.forEach(tab => {
      if (tab.getAttribute('data-setup-tab') === module) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    // Update header stats
    const catKeys = Object.keys(state.taxonomy);
    const catCount = catKeys.length;
    const activeRulesCount = state.businessRules.filter(r => r.enabled).length;

    const statCats = document.getElementById('setup-stat-categories');
    if (statCats) statCats.textContent = `${catCount} Categories`;
    const statRules = document.getElementById('setup-stat-rules');
    if (statRules) statRules.textContent = `${activeRulesCount} Active`;

    const badgeTax = document.getElementById('badge-count-taxonomy');
    if (badgeTax) badgeTax.textContent = catCount;
    const badgeRes = document.getElementById('badge-count-resolutions');
    if (badgeRes) badgeRes.textContent = state.resolutionCodes.length;
    const badgeTech = document.getElementById('badge-count-techs');
    if (badgeTech) badgeTech.textContent = state.technicians.length;
    const badgeRules = document.getElementById('badge-count-rules');
    if (badgeRules) badgeRules.textContent = state.businessRules.length;

    const container = document.getElementById('setup-modules-container');
    if (!container) return;

    if (module === 'dna') {
      container.innerHTML = renderModuleCompanyDna();
      bindModuleCompanyDnaEvents();
    } else if (module === 'taxonomy') {
      container.innerHTML = renderModuleTaxonomy();
      bindModuleTaxonomyEvents();
    } else if (module === 'matrix') {
      container.innerHTML = renderModuleMatrix();
      bindModuleMatrixEvents();
    } else if (module === 'sla') {
      container.innerHTML = renderModuleSla();
      bindModuleSlaEvents();
    } else if (module === 'resolutions') {
      container.innerHTML = renderModuleResolutions();
      bindModuleResolutionsEvents();
    } else if (module === 'technicians') {
      container.innerHTML = renderModuleTechnicians();
      bindModuleTechniciansEvents();
    } else if (module === 'rules') {
      container.innerHTML = renderModuleRules();
      bindModuleRulesEvents();
    } else if (module === 'email-channels') {
      container.innerHTML = renderModuleEmailChannels();
      bindModuleEmailChannelsEvents();
    } else if (module === 'phone-cti') {
      container.innerHTML = renderModulePhoneCti();
      bindModulePhoneCtiEvents();
    }
  }

  // --- Module 1: Taxonomy & Category Customizer ---
  function renderModuleTaxonomy() {
    const taxonomy = state.taxonomy;
    const cats = Object.keys(taxonomy);
    const selectedCat = (cats.includes(state.selectedTreeCat) ? state.selectedTreeCat : cats[0]) || '';
    const subcats = selectedCat ? Object.keys(taxonomy[selectedCat] || {}) : [];
    const selectedSub = (subcats.includes(state.selectedTreeSubcat) ? state.selectedTreeSubcat : subcats[0]) || '';
    const items = (selectedCat && selectedSub && taxonomy[selectedCat][selectedSub]) || [];

    return `
      <div class="setup-tree-container">
        <!-- Tree Hierarchy Explorer -->
        <div class="tree-card">
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <h4 style="font-size:13px; font-weight:700;">Service Taxonomy Hierarchy</h4>
            <button class="btn btn-sm btn-zen-primary" id="btn-add-category-prompt">+ New Category</button>
          </div>
          <p class="text-xs text-muted mt-1">Select a category or subcategory below to edit its terminal items.</p>
          
          <div class="tree-list">
            ${cats.map(cat => {
              const isCatSelected = cat === selectedCat;
              const catSubcats = Object.keys(taxonomy[cat] || {});
              return `
                <div class="tree-cat-node">
                  <div class="tree-cat-header ${isCatSelected ? 'selected' : ''}" data-cat="${escapeHtml(cat)}">
                    <div style="display:flex; align-items:center; gap:8px;">
                      <span>📁</span>
                      <span>${escapeHtml(cat)}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="tab-count-badge font-mono">${catSubcats.length} sub</span>
                      <button class="btn-del-chip btn-del-category" data-cat="${escapeHtml(cat)}" title="Delete Category">&times;</button>
                    </div>
                  </div>
                  ${isCatSelected ? `
                    <div class="tree-subcats-list">
                      ${catSubcats.map(sub => {
                        const isSubSelected = sub === selectedSub;
                        const subItems = taxonomy[cat][sub] || [];
                        return `
                          <div class="tree-subcat-row ${isSubSelected ? 'selected' : ''}" data-cat="${escapeHtml(cat)}" data-sub="${escapeHtml(sub)}">
                            <div style="display:flex; align-items:center; gap:6px;">
                              <span>↳ 📂</span>
                              <span>${escapeHtml(sub)}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:6px;">
                              <span class="tab-count-badge font-mono" style="font-size:9.5px;">${subItems.length} items</span>
                              <button class="btn-del-chip btn-del-subcat" data-cat="${escapeHtml(cat)}" data-sub="${escapeHtml(sub)}" title="Delete Subcategory">&times;</button>
                            </div>
                          </div>
                        `;
                      }).join('')}
                      <div style="margin-top:6px;">
                        <button class="btn btn-xs btn-zen-outline w-full" id="btn-add-subcat-inline" data-cat="${escapeHtml(cat)}">+ Add Subcategory to ${escapeHtml(cat)}</button>
                      </div>
                    </div>
                  ` : ''}
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Node Detail & Items Editor -->
        <div class="tree-detail-card">
          <div style="display:flex; align-items:center; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-zen-medium);">
            <div>
              <span class="text-xs text-muted">Active Classification Breadcrumb:</span>
              <div style="font-size:14px; font-weight:700; color:var(--text-zen-primary); display:flex; align-items:center; gap:6px; margin-top:2px;">
                <span>${escapeHtml(selectedCat)}</span>
                <span class="text-muted">➔</span>
                <span class="text-indigo">${escapeHtml(selectedSub || 'Select a Subcategory')}</span>
              </div>
            </div>
            <span class="badge-tag">Reactive Live Sync</span>
          </div>

          ${selectedSub ? `
            <div class="mt-3">
              <h5 style="font-size:12px; font-weight:700; color:var(--text-zen-secondary); text-transform:uppercase; letter-spacing:0.03em;">
                Specific Items in "${escapeHtml(selectedSub)}" (${items.length})
              </h5>
              <p class="text-xs text-muted mt-1">These terminal items appear directly in Tier-3 classification dropdowns.</p>

              <!-- Add Item Form -->
              <form id="form-add-tree-item" style="display:flex; gap:8px; margin-top:12px;">
                <input type="text" id="input-new-tree-item" class="zen-form-control" placeholder="Add specific failure or service item..." required style="height:34px;">
                <button type="submit" class="btn btn-sm btn-zen-primary" style="white-space:nowrap;">+ Add Item</button>
              </form>

              <!-- Items Chips List -->
              <div class="tree-items-chips mt-3">
                ${items.length > 0 ? items.map(itm => `
                  <span class="tree-item-chip">
                    <span>${escapeHtml(itm)}</span>
                    <button type="button" class="btn-del-chip btn-del-tree-item" data-cat="${escapeHtml(selectedCat)}" data-sub="${escapeHtml(selectedSub)}" data-item="${escapeHtml(itm)}" title="Delete item">&times;</button>
                  </span>
                `).join('') : `
                  <div class="text-xs text-muted" style="padding:12px; background:var(--bg-zen-subtle); border-radius:6px; width:100%;">
                    No items configured for this subcategory yet. Add one using the form above.
                  </div>
                `}
              </div>
            </div>
          ` : `
            <div style="padding:30px; text-align:center; color:var(--text-zen-muted); font-size:13px;">
              Select a subcategory on the left to manage items.
            </div>
          `}

          <!-- Live Cascading Preview Widget -->
          <div style="margin-top:24px; padding:16px; background:var(--bg-zen-subtle); border:1px solid var(--border-zen-medium); border-radius:8px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
              <strong style="font-size:11.5px; text-transform:uppercase; letter-spacing:0.03em; color:var(--text-zen-secondary);">Interactive Cascading Preview</strong>
              <span class="badge-gem-dot"></span>
            </div>
            <p class="text-xs text-muted mb-2">Simulate cascading selection in real-time as users will experience it:</p>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">
              <div>
                <label class="text-xs text-muted">Category</label>
                <select id="preview-tree-cat" class="zen-select w-full" style="height:32px; font-size:12px;"></select>
              </div>
              <div>
                <label class="text-xs text-muted">Subcategory</label>
                <select id="preview-tree-subcat" class="zen-select w-full" style="height:32px; font-size:12px;"></select>
              </div>
              <div>
                <label class="text-xs text-muted">Item</label>
                <select id="preview-tree-item" class="zen-select w-full" style="height:32px; font-size:12px;"></select>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function bindModuleTaxonomyEvents() {
    // Select Category
    document.querySelectorAll('.tree-cat-header').forEach(header => {
      header.addEventListener('click', (e) => {
        if (e.target.closest('.btn-del-category')) return;
        const cat = header.getAttribute('data-cat');
        state.selectedTreeCat = cat;
        const subcats = Object.keys(state.taxonomy[cat] || {});
        state.selectedTreeSubcat = subcats[0] || '';
        renderSetupCenter('taxonomy');
      });
    });

    // Select Subcategory
    document.querySelectorAll('.tree-subcat-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('.btn-del-subcat')) return;
        state.selectedTreeCat = row.getAttribute('data-cat');
        state.selectedTreeSubcat = row.getAttribute('data-sub');
        renderSetupCenter('taxonomy');
      });
    });

    // Add Category
    const btnAddCat = document.getElementById('btn-add-category-prompt');
    if (btnAddCat) {
      btnAddCat.addEventListener('click', () => {
        const name = prompt('Enter new Category name (e.g., Identity & Directory Services, Data Analytics):');
        if (name && name.trim()) {
          const trimmed = name.trim();
          if (!state.taxonomy[trimmed]) {
            state.taxonomy[trimmed] = {};
            state.selectedTreeCat = trimmed;
            state.selectedTreeSubcat = '';
            refreshTaxonomyInUI();
            renderSetupCenter('taxonomy');
            showToast(`Category "${trimmed}" created! Add subcategories now.`, 'success');
          } else {
            showToast(`Category "${trimmed}" already exists.`, 'error');
          }
        }
      });
    }

    // Delete Category
    document.querySelectorAll('.btn-del-category').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const cat = btn.getAttribute('data-cat');
        if (confirm(`Delete Category "${cat}" and all its child items?`)) {
          delete state.taxonomy[cat];
          const remaining = Object.keys(state.taxonomy);
          state.selectedTreeCat = remaining[0] || '';
          state.selectedTreeSubcat = state.selectedTreeCat ? Object.keys(state.taxonomy[state.selectedTreeCat])[0] || '' : '';
          refreshTaxonomyInUI();
          renderSetupCenter('taxonomy');
          showToast(`Category "${cat}" removed.`, 'info');
        }
      });
    });

    // Add Subcategory
    const btnAddSub = document.getElementById('btn-add-subcat-inline');
    if (btnAddSub) {
      btnAddSub.addEventListener('click', () => {
        const cat = btnAddSub.getAttribute('data-cat');
        const name = prompt(`Enter new Subcategory for "${cat}" (e.g. DynamoDB, Ingress Envoy):`);
        if (name && name.trim()) {
          const trimmed = name.trim();
          if (!state.taxonomy[cat]) state.taxonomy[cat] = {};
          if (!state.taxonomy[cat][trimmed]) {
            state.taxonomy[cat][trimmed] = [];
            state.selectedTreeCat = cat;
            state.selectedTreeSubcat = trimmed;
            refreshTaxonomyInUI();
            renderSetupCenter('taxonomy');
            showToast(`Subcategory "${trimmed}" added to "${cat}".`, 'success');
          } else {
            showToast(`Subcategory "${trimmed}" already exists.`, 'error');
          }
        }
      });
    }

    // Delete Subcategory
    document.querySelectorAll('.btn-del-subcat').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const cat = btn.getAttribute('data-cat');
        const sub = btn.getAttribute('data-sub');
        if (confirm(`Delete Subcategory "${sub}"?`)) {
          if (state.taxonomy[cat]) {
            delete state.taxonomy[cat][sub];
          }
          const remainingSubs = Object.keys(state.taxonomy[cat] || {});
          state.selectedTreeSubcat = remainingSubs[0] || '';
          refreshTaxonomyInUI();
          renderSetupCenter('taxonomy');
          showToast(`Subcategory "${sub}" removed.`, 'info');
        }
      });
    });

    // Add Item Form
    const formAddItem = document.getElementById('form-add-tree-item');
    if (formAddItem) {
      formAddItem.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('input-new-tree-item');
        const itemText = input ? input.value.trim() : '';
        if (!itemText) return;
        const cat = state.selectedTreeCat;
        const sub = state.selectedTreeSubcat;
        if (cat && sub && state.taxonomy[cat] && state.taxonomy[cat][sub]) {
          state.taxonomy[cat][sub].push(itemText);
          refreshTaxonomyInUI();
          renderSetupCenter('taxonomy');
          showToast(`Added item "${itemText}" to ${sub}.`, 'success');
        }
      });
    }

    // Delete Item
    document.querySelectorAll('.btn-del-tree-item').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const cat = btn.getAttribute('data-cat');
        const sub = btn.getAttribute('data-sub');
        const itm = btn.getAttribute('data-item');
        if (state.taxonomy[cat] && state.taxonomy[cat][sub]) {
          state.taxonomy[cat][sub] = state.taxonomy[cat][sub].filter(i => i !== itm);
          refreshTaxonomyInUI();
          renderSetupCenter('taxonomy');
          showToast(`Item "${itm}" removed.`, 'info');
        }
      });
    });

    // Populate Live Preview Dropdowns
    const prevCat = document.getElementById('preview-tree-cat');
    const prevSub = document.getElementById('preview-tree-subcat');
    const prevItm = document.getElementById('preview-tree-item');
    if (prevCat && prevSub && prevItm) {
      populateClassificationDropdowns(prevCat, prevSub, prevItm, state.selectedTreeCat, state.selectedTreeSubcat);
    }
  }

  // --- Module 2: Priority Matrix Grid Editor ---
  function renderModuleMatrix() {
    const impacts = ['Enterprise', 'Department', 'Single User'];
    const urgencies = ['Critical', 'High', 'Medium', 'Low'];
    const matrix = state.priorityMatrix;
    const slaPolicies = state.slaPolicies;

    return `
      <div class="matrix-grid-card">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">Dynamic Impact × Urgency Priority Matrix</h4>
            <p class="text-xs text-muted mt-1">Configure severity calculation cells. Changing any mapping instantly propagates to the ticket intake forms.</p>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-sm btn-zen-outline" id="btn-reset-matrix">Reset to Standard ITIL Defaults</button>
          </div>
        </div>

        <div style="overflow-x:auto;">
          <table class="setup-matrix-table">
            <thead>
              <tr>
                <th width="160">Impact \\ Urgency</th>
                ${urgencies.map(u => `<th>${u}</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${impacts.map(imp => `
                <tr>
                  <td style="text-align:left; font-weight:700; background:var(--bg-zen-subtle); color:var(--text-zen-primary); font-size:12.5px;">
                    ${imp}
                  </td>
                  ${urgencies.map(urg => {
                    const currentP = (matrix[imp] && matrix[imp][urg]) || 'P3';
                    const slaHours = slaPolicies[currentP]?.resolveHours || 4;
                    return `
                      <td>
                        <div class="matrix-cell-content">
                          <select class="zen-select matrix-cell-select" data-impact="${imp}" data-urgency="${urg}">
                            <option value="P1" ${currentP === 'P1' ? 'selected' : ''}>P1 Critical</option>
                            <option value="P2" ${currentP === 'P2' ? 'selected' : ''}>P2 High</option>
                            <option value="P3" ${currentP === 'P3' ? 'selected' : ''}>P3 Medium</option>
                            <option value="P4" ${currentP === 'P4' ? 'selected' : ''}>P4 Low</option>
                          </select>
                          <span class="matrix-sla-badge">${slaHours}h Target</span>
                        </div>
                      </td>
                    `;
                  }).join('')}
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>

        <!-- SLA Resolution Hours Target per Priority Tier -->
        <div style="margin-top:18px;">
          <h5 style="font-size:12.5px; font-weight:700; color:var(--text-zen-secondary); text-transform:uppercase; letter-spacing:0.03em;">
            Resolution SLA Target Hours per Tier
          </h5>
          <div class="matrix-sla-hours-grid">
            ${['P1', 'P2', 'P3', 'P4'].map(p => {
              const pol = slaPolicies[p] || { resolveHours: 4, responseMins: 30 };
              return `
                <div style="background:var(--bg-zen-subtle); border:1px solid var(--border-zen-medium); border-radius:8px; padding:12px;">
                  <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span class="priority-pill pill-${p.toLowerCase()}">${p}</span>
                    <span class="text-xs text-muted font-bold">${pol.name || p}</span>
                  </div>
                  <div class="form-group mt-2 mb-0">
                    <label class="text-xs text-muted">Resolve Target (Hours)</label>
                    <input type="number" class="zen-form-control input-sla-hours font-mono" data-priority="${p}" value="${pol.resolveHours}" min="1" max="168" style="height:32px;">
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function bindModuleMatrixEvents() {
    // Cell priority select change
    document.querySelectorAll('.matrix-cell-select').forEach(sel => {
      sel.addEventListener('change', () => {
        const imp = sel.getAttribute('data-impact');
        const urg = sel.getAttribute('data-urgency');
        const newP = sel.value;
        if (!state.priorityMatrix[imp]) state.priorityMatrix[imp] = {};
        state.priorityMatrix[imp][urg] = newP;
        refreshMatrixInUI();
        renderSetupCenter('matrix');
        showToast(`Priority Matrix updated: ${imp} × ${urg} = ${newP}`, 'success');
      });
    });

    // SLA Hours input change
    document.querySelectorAll('.input-sla-hours').forEach(input => {
      input.addEventListener('change', () => {
        const p = input.getAttribute('data-priority');
        const val = parseInt(input.value, 10) || 4;
        if (!state.slaPolicies[p]) state.slaPolicies[p] = {};
        state.slaPolicies[p].resolveHours = val;
        renderSetupCenter('matrix');
        showToast(`Updated ${p} SLA resolution target to ${val} hours.`, 'info');
      });
    });

    // Reset matrix
    const btnReset = document.getElementById('btn-reset-matrix');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        state.priorityMatrix = JSON.parse(JSON.stringify(DEFAULT_PRIORITY_MATRIX));
        refreshMatrixInUI();
        renderSetupCenter('matrix');
        showToast('Priority Matrix reset to standard ITIL defaults.', 'info');
      });
    }
  }

  // --- Module 3: SLA Policies & Business Hours ---
  function renderModuleSla() {
    const schedules = state.slaSchedules;
    return `
      <div class="setup-sla-grid">
        <!-- Calendar Schedule Card -->
        <div class="sla-policy-card">
          <div>
            <h4 style="font-size:13.5px; font-weight:700;">Operational Calendar &amp; Coverage Schedules</h4>
            <p class="text-xs text-muted mt-1">Define whether SLA timers count down 24x7 or only during office hours.</p>
          </div>

          <div class="form-group">
            <label class="text-xs font-bold text-secondary">Active Coverage Schedule</label>
            <select id="select-sla-schedule-mode" class="zen-select w-full" style="height:34px;">
              <option value="24x7" ${schedules.scheduleMode === '24x7' ? 'selected' : ''}>24x7 Continuous SRE Coverage (Default)</option>
              <option value="business" ${schedules.scheduleMode === 'business' ? 'selected' : ''}>Standard Business Hours (9:00 AM - 6:00 PM EST, Mon-Fri)</option>
              <option value="follow-sun" ${schedules.scheduleMode === 'follow-sun' ? 'selected' : ''}>Follow-the-Sun Global Shift Rotation</option>
            </select>
          </div>

          <div class="form-group">
            <label class="text-xs font-bold text-secondary">Primary Timezone</label>
            <select id="select-sla-timezone" class="zen-select w-full" style="height:34px;">
              <option value="UTC" ${schedules.timezone === 'UTC' ? 'selected' : ''}>UTC (Coordinated Universal Time)</option>
              <option value="America/New_York" ${schedules.timezone === 'America/New_York' ? 'selected' : ''}>America/New_York (EST / EDT)</option>
              <option value="Europe/London" ${schedules.timezone === 'Europe/London' ? 'selected' : ''}>Europe/London (GMT / BST)</option>
              <option value="Asia/Tokyo" ${schedules.timezone === 'Asia/Tokyo' ? 'selected' : ''}>Asia/Tokyo (JST)</option>
              <option value="Asia/Kolkata" ${schedules.timezone === 'Asia/Kolkata' ? 'selected' : ''}>Asia/Kolkata (IST)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="toggle-switch-label">
              <span>Auto-pause SLAs during Regional Holidays</span>
              <input type="checkbox" id="check-sla-holidays" class="zen-checkbox" checked>
            </label>
          </div>
        </div>

        <!-- SLA Pause Conditions & Escalation Timers -->
        <div class="sla-policy-card">
          <div>
            <h4 style="font-size:13.5px; font-weight:700;">Pause Conditions &amp; Warning Thresholds</h4>
            <p class="text-xs text-muted mt-1">Configure automated clock freezing conditions and breach alerts.</p>
          </div>

          <div style="display:flex; flex-direction:column; gap:8px;">
            <label class="toggle-switch-label">
              <span>Pause timer when ticket is set to <strong>ON_HOLD</strong></span>
              <input type="checkbox" id="check-pause-onhold" class="zen-checkbox" ${schedules.pauseOnHold ? 'checked' : ''}>
            </label>
            <label class="toggle-switch-label">
              <span>Allow pause for <strong>Pending Customer</strong> response</span>
              <input type="checkbox" id="check-pause-customer" class="zen-checkbox" ${schedules.pausePendingCustomer ? 'checked' : ''}>
            </label>
            <label class="toggle-switch-label">
              <span>Allow pause for <strong>Pending Vendor</strong> dependency</span>
              <input type="checkbox" id="check-pause-vendor" class="zen-checkbox" ${schedules.pausePendingVendor ? 'checked' : ''}>
            </label>
            <label class="toggle-switch-label">
              <span>Allow pause for <strong>Pending Change Approval (CAB)</strong></span>
              <input type="checkbox" id="check-pause-change" class="zen-checkbox" ${schedules.pausePendingChange ? 'checked' : ''}>
            </label>
          </div>

          <div class="form-row-2 mt-2">
            <div class="form-group mb-0">
              <label class="text-xs text-muted">P1 Near-Breach Alert Threshold</label>
              <input type="number" id="input-p1-thresh" class="zen-form-control font-mono" value="${schedules.p1ThresholdMins || 30}" min="5" max="120" style="height:32px;">
            </div>
            <div class="form-group mb-0">
              <label class="text-xs text-muted">P2 Near-Breach Alert Threshold</label>
              <input type="number" id="input-p2-thresh" class="zen-form-control font-mono" value="${schedules.p2ThresholdMins || 60}" min="10" max="240" style="height:32px;">
            </div>
          </div>

          <button class="btn btn-sm btn-zen-primary mt-2" id="btn-save-sla-settings">Save SLA Policy Settings</button>
        </div>
      </div>
    `;
  }

  function bindModuleSlaEvents() {
    const btnSave = document.getElementById('btn-save-sla-settings');
    if (btnSave) {
      btnSave.addEventListener('click', () => {
        state.slaSchedules.scheduleMode = document.getElementById('select-sla-schedule-mode').value;
        state.slaSchedules.timezone = document.getElementById('select-sla-timezone').value;
        state.slaSchedules.pauseOnHold = document.getElementById('check-pause-onhold').checked;
        state.slaSchedules.pausePendingCustomer = document.getElementById('check-pause-customer').checked;
        state.slaSchedules.pausePendingVendor = document.getElementById('check-pause-vendor').checked;
        state.slaSchedules.pausePendingChange = document.getElementById('check-pause-change').checked;
        state.slaSchedules.p1ThresholdMins = parseInt(document.getElementById('input-p1-thresh').value, 10) || 30;
        state.slaSchedules.p2ThresholdMins = parseInt(document.getElementById('input-p2-thresh').value, 10) || 60;
        showToast('SLA schedules, pause conditions & thresholds saved successfully!', 'success');
      });
    }
  }

  // --- Module 4: Resolution Codes & Root Causes ---
  function renderModuleResolutions() {
    const codes = state.resolutionCodes;
    const causes = state.rootCauses;

    return `
      <div class="setup-resolutions-grid">
        <!-- Resolution Codes Manager -->
        <div class="res-master-card">
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <h4 style="font-size:13.5px; font-weight:700;">Standard Resolution Codes (${codes.length})</h4>
            <span class="badge-tag">ITIL Master Data</span>
          </div>
          <p class="text-xs text-muted mt-1">Codes required by technicians to close out incidents in the Resolve dialog.</p>

          <form id="form-add-res-code" style="display:flex; gap:8px; margin-top:14px;">
            <input type="text" id="input-new-res-code" class="zen-form-control" placeholder="Add resolution code (e.g. Firmware Rollback)..." required style="height:34px;">
            <button type="submit" class="btn btn-sm btn-zen-primary" style="white-space:nowrap;">+ Add</button>
          </form>

          <div class="res-items-list" id="res-codes-list">
            ${codes.map((code, idx) => `
              <div class="res-item-row">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="text-emerald font-bold">✓</span>
                  <span>${escapeHtml(code)}</span>
                </div>
                <button class="btn-del-chip btn-del-res-code" data-index="${idx}" title="Delete Code">&times;</button>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Root Cause Categories Manager -->
        <div class="res-master-card">
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <h4 style="font-size:13.5px; font-weight:700;">Root Cause Master Data (${causes.length})</h4>
            <span class="badge-tag">RCA Taxonomies</span>
          </div>
          <p class="text-xs text-muted mt-1">Categorical root causes for Post-Incident Reviews (PIR) and problem management.</p>

          <form id="form-add-root-cause" style="display:flex; gap:8px; margin-top:14px;">
            <input type="text" id="input-new-root-cause" class="zen-form-control" placeholder="Add root cause (e.g. Memory Leak, Core Dump)..." required style="height:34px;">
            <button type="submit" class="btn btn-sm btn-zen-primary" style="white-space:nowrap;">+ Add</button>
          </form>

          <div class="res-items-list" id="root-causes-list">
            ${causes.map((cause, idx) => `
              <div class="res-item-row">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="text-indigo font-bold">🔍</span>
                  <span>${escapeHtml(cause)}</span>
                </div>
                <button class="btn-del-chip btn-del-root-cause" data-index="${idx}" title="Delete Cause">&times;</button>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function bindModuleResolutionsEvents() {
    // Add resolution code
    const formAddCode = document.getElementById('form-add-res-code');
    if (formAddCode) {
      formAddCode.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('input-new-res-code');
        const val = input ? input.value.trim() : '';
        if (!val) return;
        if (!state.resolutionCodes.includes(val)) {
          state.resolutionCodes.push(val);
          refreshResolutionCodesInUI();
          renderSetupCenter('resolutions');
          showToast(`Resolution Code "${val}" added to master data.`, 'success');
        } else {
          showToast(`Resolution Code "${val}" already exists.`, 'error');
        }
      });
    }

    // Delete resolution code
    document.querySelectorAll('.btn-del-res-code').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-index'), 10);
        const code = state.resolutionCodes[idx];
        state.resolutionCodes.splice(idx, 1);
        refreshResolutionCodesInUI();
        renderSetupCenter('resolutions');
        showToast(`Removed Resolution Code "${code}".`, 'info');
      });
    });

    // Add root cause
    const formAddCause = document.getElementById('form-add-root-cause');
    if (formAddCause) {
      formAddCause.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('input-new-root-cause');
        const val = input ? input.value.trim() : '';
        if (!val) return;
        if (!state.rootCauses.includes(val)) {
          state.rootCauses.push(val);
          renderSetupCenter('resolutions');
          showToast(`Root Cause "${val}" added to master data.`, 'success');
        }
      });
    }

    // Delete root cause
    document.querySelectorAll('.btn-del-root-cause').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-index'), 10);
        const cause = state.rootCauses[idx];
        state.rootCauses.splice(idx, 1);
        renderSetupCenter('resolutions');
        showToast(`Removed Root Cause "${cause}".`, 'info');
      });
    });
  }

  // --- Module 5: Technician Roster & Labor Rates ---
  function renderModuleTechnicians() {
    const techs = state.technicians;
    return `
      <div class="tech-roster-card">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">Technician Roster &amp; Labor Billing Rates</h4>
            <p class="text-xs text-muted mt-1">Configure staff profiles, assigned support groups, and hourly billing rates for worklog accounting.</p>
          </div>
        </div>

        <!-- Add Technician Form -->
        <div style="background:var(--bg-zen-subtle); border:1px solid var(--border-zen-medium); border-radius:8px; padding:14px; margin-top:14px;">
          <span style="font-size:12px; font-weight:700; color:var(--text-zen-secondary); text-transform:uppercase; letter-spacing:0.03em;">Add New Technician Profile</span>
          <form id="form-add-technician" style="display:grid; grid-template-columns: 1.5fr 1.5fr 1.5fr 1fr 1fr auto; gap:8px; margin-top:8px; align-items:end;">
            <div>
              <label class="text-xs text-muted">Full Name</label>
              <input type="text" id="tech-input-name" class="zen-form-control" placeholder="e.g. Jordan Reed" required style="height:32px;">
            </div>
            <div>
              <label class="text-xs text-muted">Title / Role</label>
              <input type="text" id="tech-input-role" class="zen-form-control" placeholder="e.g. Senior SRE" required style="height:32px;">
            </div>
            <div>
              <label class="text-xs text-muted">Support Group</label>
              <select id="tech-input-group" class="zen-select w-full" style="height:32px;">
                <option value="SRE-Core">SRE Core</option>
                <option value="Database-Ops">Database Ops</option>
                <option value="Payment-Platform">Payment Platform</option>
                <option value="Cloud-Infra">Cloud Infra</option>
                <option value="Security-SecOps">Security SecOps</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-muted">Rate ($/hr)</label>
              <input type="number" id="tech-input-rate" class="zen-form-control font-mono" value="150" min="0" step="5" required style="height:32px;">
            </div>
            <div>
              <label class="text-xs text-muted">Status</label>
              <select id="tech-input-status" class="zen-select w-full" style="height:32px;">
                <option value="Active">Active</option>
                <option value="On Leave">On Leave</option>
              </select>
            </div>
            <div>
              <button type="submit" class="btn btn-sm btn-zen-primary" style="height:32px;">+ Add Tech</button>
            </div>
          </form>
        </div>

        <!-- Technicians Table -->
        <div style="overflow-x:auto;">
          <table class="tech-table">
            <thead>
              <tr>
                <th width="240">Technician</th>
                <th>Role &amp; Title</th>
                <th>Support Group</th>
                <th width="140">Billing Rate</th>
                <th width="120">Status</th>
                <th width="90" class="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              ${techs.map(t => `
                <tr>
                  <td>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <span class="tech-avatar-mini">${escapeHtml(t.name.substring(0, 2).toUpperCase())}</span>
                      <strong style="color:var(--text-zen-primary);">${escapeHtml(t.name)}</strong>
                    </div>
                  </td>
                  <td class="text-secondary">${escapeHtml(t.role)}</td>
                  <td><span class="badge-tag">${escapeHtml(t.group)}</span></td>
                  <td><strong class="font-mono text-emerald">$${t.rate}/hr</strong></td>
                  <td>
                    <span class="${t.status === 'Active' ? 'badge-billable' : 'badge-nonbillable'}">${escapeHtml(t.status)}</span>
                  </td>
                  <td class="text-right">
                    <button class="btn-del-chip btn-del-technician" data-tech-id="${t.id}" title="Remove Technician">&times;</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  function bindModuleTechniciansEvents() {
    // Add technician
    const formTech = document.getElementById('form-add-technician');
    if (formTech) {
      formTech.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('tech-input-name').value.trim();
        const role = document.getElementById('tech-input-role').value.trim();
        const group = document.getElementById('tech-input-group').value;
        const rate = parseFloat(document.getElementById('tech-input-rate').value) || 150;
        const status = document.getElementById('tech-input-status').value;

        if (!name || !role) return;

        const newTech = {
          id: `TECH-${Date.now()}`,
          name: name,
          role: role,
          group: group,
          rate: rate,
          status: status
        };

        state.technicians.push(newTech);
        refreshTechniciansInUI();
        renderSetupCenter('technicians');
        showToast(`Registered technician ${name} (${group} @ $${rate}/hr).`, 'success');
      });
    }

    // Delete technician
    document.querySelectorAll('.btn-del-technician').forEach(btn => {
      btn.addEventListener('click', () => {
        const techId = btn.getAttribute('data-tech-id');
        const t = state.technicians.find(x => x.id === techId);
        state.technicians = state.technicians.filter(x => x.id !== techId);
        refreshTechniciansInUI();
        renderSetupCenter('technicians');
        showToast(`Technician ${t ? t.name : ''} removed from roster.`, 'info');
      });
    });
  }

  // --- Module 6: Business Rules Automation Builder ---
  function renderModuleRules() {
    const rules = state.businessRules;
    const cats = Object.keys(state.taxonomy);

    return `
      <div class="rules-builder-card">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">Conditional Business Rules Engine</h4>
            <p class="text-xs text-muted mt-1">Automate routing and severity determination. Rules trigger sequentially on incident intake.</p>
          </div>
        </div>

        <!-- Add Rule Card -->
        <div style="background:var(--bg-zen-subtle); border:1px solid var(--border-zen-medium); border-radius:8px; padding:14px; margin-top:14px;">
          <span style="font-size:12px; font-weight:700; color:var(--text-zen-secondary); text-transform:uppercase; letter-spacing:0.03em;">Deploy New Automation Rule</span>
          <form id="form-add-business-rule" style="margin-top:10px; display:flex; flex-direction:column; gap:10px;">
            <div class="form-row-2">
              <div>
                <label class="text-xs text-muted">Rule Name / Description</label>
                <input type="text" id="rule-input-name" class="zen-form-control" placeholder="e.g. Route Authentication Incidents to SecOps" required style="height:32px;">
              </div>
              <div>
                <label class="text-xs text-muted">IF Field Equals</label>
                <div style="display:flex; gap:6px;">
                  <select id="rule-input-field" class="zen-select" style="height:32px; width:120px;">
                    <option value="category">Category</option>
                    <option value="ci">Affected CI</option>
                  </select>
                  <select id="rule-input-val" class="zen-select w-full" style="height:32px;">
                    ${cats.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
                  </select>
                </div>
              </div>
            </div>

            <div class="form-row-2">
              <div>
                <label class="text-xs text-muted">THEN Set Assignment Group To</label>
                <select id="rule-input-target-team" class="zen-select w-full" style="height:32px;">
                  <option value="Database-Ops">Database-Ops</option>
                  <option value="SRE-Core">SRE-Core</option>
                  <option value="Payment-Platform">Payment-Platform</option>
                  <option value="Cloud-Infra">Cloud-Infra</option>
                  <option value="Security-SecOps">Security-SecOps</option>
                </select>
              </div>
              <div>
                <label class="text-xs text-muted">AND Set Calculated Priority To</label>
                <select id="rule-input-target-priority" class="zen-select w-full" style="height:32px;">
                  <option value="P1">P1 Critical</option>
                  <option value="P2">P2 High</option>
                  <option value="P3">P3 Moderate</option>
                  <option value="P4">P4 Low</option>
                </select>
              </div>
            </div>

            <div style="text-align:right;">
              <button type="submit" class="btn btn-sm btn-zen-primary">+ Deploy Business Rule</button>
            </div>
          </form>
        </div>

        <!-- Active Rules List -->
        <div class="rules-list">
          ${rules.map(r => `
            <div class="rule-card-item ${!r.enabled ? 'disabled' : ''}">
              <div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <strong style="color:var(--text-zen-primary); font-size:13px;">${escapeHtml(r.name)}</strong>
                  <span class="badge-tag">${r.enabled ? 'Active' : 'Disabled'}</span>
                </div>
                <div class="rule-statement">
                  <span class="rule-kw">IF</span>
                  <span class="rule-pill">${r.conditionField}</span>
                  <span class="text-muted">equals</span>
                  <span class="rule-pill text-indigo font-bold">${escapeHtml(r.conditionValue)}</span>
                  <span class="rule-kw">THEN</span>
                  <span class="text-muted">Route to</span>
                  <span class="rule-pill text-emerald font-bold">${escapeHtml(r.targetTeam)}</span>
                  <span class="text-muted">&amp; Set</span>
                  <span class="priority-pill pill-${r.targetPriority.toLowerCase()}">${r.targetPriority}</span>
                </div>
              </div>
              <div style="display:flex; align-items:center; gap:10px;">
                <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:12px;">
                  <input type="checkbox" class="zen-checkbox toggle-rule-enabled" data-rule-id="${r.id}" ${r.enabled ? 'checked' : ''}>
                  <span>Enabled</span>
                </label>
                <button class="btn-del-chip btn-del-rule" data-rule-id="${r.id}" title="Delete Rule">&times;</button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  function bindModuleRulesEvents() {
    const fieldSelect = document.getElementById('rule-input-field');
    const valSelect = document.getElementById('rule-input-val');
    if (fieldSelect && valSelect) {
      fieldSelect.addEventListener('change', () => {
        if (fieldSelect.value === 'category') {
          valSelect.innerHTML = Object.keys(state.taxonomy).map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
        } else {
          valSelect.innerHTML = state.cmdbNodes.map(n => `<option value="${escapeHtml(n.id)}">${escapeHtml(n.name)} (${n.id})</option>`).join('');
        }
      });
    }

    const formRule = document.getElementById('form-add-business-rule');
    if (formRule) {
      formRule.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('rule-input-name').value.trim();
        const field = document.getElementById('rule-input-field').value;
        const val = document.getElementById('rule-input-val').value;
        const targetTeam = document.getElementById('rule-input-target-team').value;
        const targetPriority = document.getElementById('rule-input-target-priority').value;

        if (!name) return;

        const newRule = {
          id: `BR-${Date.now()}`,
          name: name,
          enabled: true,
          conditionField: field,
          conditionOperator: 'equals',
          conditionValue: val,
          targetTeam: targetTeam,
          targetPriority: targetPriority
        };

        state.businessRules.unshift(newRule);
        renderSetupCenter('rules');
        showToast(`Deployed Business Rule "${name}"!`, 'success');
      });
    }

    // Toggle rule enabled
    document.querySelectorAll('.toggle-rule-enabled').forEach(chk => {
      chk.addEventListener('change', () => {
        const rId = chk.getAttribute('data-rule-id');
        const rule = state.businessRules.find(r => r.id === rId);
        if (rule) {
          rule.enabled = chk.checked;
          renderSetupCenter('rules');
          showToast(`Rule "${rule.name}" is now ${rule.enabled ? 'Active' : 'Disabled'}.`, 'info');
        }
      });
    });

    // Delete rule
    document.querySelectorAll('.btn-del-rule').forEach(btn => {
      btn.addEventListener('click', () => {
        const rId = btn.getAttribute('data-rule-id');
        const rule = state.businessRules.find(r => r.id === rId);
        state.businessRules = state.businessRules.filter(r => r.id !== rId);
        renderSetupCenter('rules');
        showToast(`Deleted rule "${rule ? rule.name : ''}".`, 'info');
      });
    });
  }

  // --- Real-time Reactivity Propagation Helpers ---
  function refreshTaxonomyInUI() {
    CLASSIFICATION_DATA = state.taxonomy;
    if (DOM.selectTicketCategory && DOM.selectTicketSubcategory && DOM.selectTicketItem) {
      populateClassificationDropdowns(DOM.selectTicketCategory, DOM.selectTicketSubcategory, DOM.selectTicketItem);
    }
    const drawerCat = document.getElementById('drawer-cat-select');
    const drawerSubcat = document.getElementById('drawer-subcat-select');
    const drawerItem = document.getElementById('drawer-item-select');
    if (drawerCat && drawerSubcat && drawerItem && state.selectedTicket) {
      populateClassificationDropdowns(drawerCat, drawerSubcat, drawerItem, state.selectedTicket.category, state.selectedTicket.subcategory, state.selectedTicket.item);
    }
    const countBadge = document.getElementById('badge-count-taxonomy');
    if (countBadge) countBadge.textContent = Object.keys(state.taxonomy).length;
    const statCat = document.getElementById('setup-stat-categories');
    if (statCat) statCat.textContent = `${Object.keys(state.taxonomy).length} Categories`;
  }

  function refreshMatrixInUI() {
    if (DOM.selectTicketImpact && DOM.selectTicketUrgency) {
      const p = calculatePriority(DOM.selectTicketImpact.value, DOM.selectTicketUrgency.value);
      if (DOM.createPriorityPreviewBadge) {
        DOM.createPriorityPreviewBadge.className = `priority-pill pill-${p.toLowerCase()}`;
        DOM.createPriorityPreviewBadge.textContent = p;
      }
      if (DOM.createPriorityCalcLabel) {
        DOM.createPriorityCalcLabel.textContent = `${DOM.selectTicketImpact.value} × ${DOM.selectTicketUrgency.value} = ${p}`;
      }
      if (DOM.selectTicketPriority) {
        DOM.selectTicketPriority.value = p;
      }
    }
    const drawerImpact = document.getElementById('drawer-impact-select');
    const drawerUrgency = document.getElementById('drawer-urgency-select');
    const drawerBadge = document.getElementById('drawer-matrix-badge');
    const drawerLabel = document.getElementById('drawer-matrix-label');
    if (drawerImpact && drawerUrgency && drawerBadge) {
      const p = calculatePriority(drawerImpact.value, drawerUrgency.value);
      drawerBadge.className = `priority-pill pill-${p.toLowerCase()}`;
      drawerBadge.textContent = p;
      if (drawerLabel) {
        drawerLabel.textContent = `${drawerImpact.value} × ${drawerUrgency.value} = ${p}`;
      }
      if (state.selectedTicket) {
        state.selectedTicket.priority = p;
        const headerBadge = document.getElementById('drawer-header-priority-pill');
        if (headerBadge) {
          headerBadge.className = `priority-pill pill-${p.toLowerCase()}`;
          headerBadge.textContent = p;
        }
      }
    }
  }

  function refreshResolutionCodesInUI() {
    const resSelect = document.getElementById('select-resolution-code');
    if (resSelect) {
      resSelect.innerHTML = state.resolutionCodes.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    }
    const badgeRes = document.getElementById('badge-count-resolutions');
    if (badgeRes) badgeRes.textContent = state.resolutionCodes.length;
  }

  function refreshTechniciansInUI() {
    const wlTechSelect = document.getElementById('input-wl-tech');
    if (wlTechSelect) {
      wlTechSelect.innerHTML = state.technicians.map(t => `<option value="${escapeHtml(t.name)}" data-rate="${t.rate}">${escapeHtml(t.name)} ($${t.rate}/hr)</option>`).join('');
      const selectedOpt = wlTechSelect.options[wlTechSelect.selectedIndex];
      const r = selectedOpt ? selectedOpt.getAttribute('data-rate') : null;
      const rateInput = document.getElementById('input-wl-rate');
      if (r && rateInput) rateInput.value = r;
    }
    const subtaskAssigneeSelect = document.getElementById('input-subtask-assignee');
    if (subtaskAssigneeSelect) {
      subtaskAssigneeSelect.innerHTML = state.technicians.map(t => `<option value="${escapeHtml(t.name)}">${escapeHtml(t.name)}</option>`).join('') + '<option value="Unassigned">Unassigned</option>';
    }
    const badgeTech = document.getElementById('badge-count-techs');
    if (badgeTech) badgeTech.textContent = state.technicians.length;
  }

  function evaluateBusinessRules(category, ci) {
    if (!state.businessRules) return null;
    for (const rule of state.businessRules) {
      if (!rule.enabled) continue;
      if (rule.conditionField === 'category' && rule.conditionValue === category) {
        return rule;
      }
      if (rule.conditionField === 'ci' && rule.conditionValue === ci) {
        return rule;
      }
    }
    return null;
  }

  function applyBusinessRuleToCreateModal() {
    if (!DOM.selectTicketCategory) return;
    const cat = DOM.selectTicketCategory.value;
    const ci = DOM.selectTicketCi ? DOM.selectTicketCi.value : '';
    const matchedRule = evaluateBusinessRules(cat, ci);
    if (matchedRule) {
      if (matchedRule.targetTeam && DOM.selectTicketTeam) {
        DOM.selectTicketTeam.value = matchedRule.targetTeam;
      }
      if (matchedRule.targetPriority && DOM.selectTicketPriority) {
        if (matchedRule.targetPriority === 'P1') {
          DOM.selectTicketImpact.value = 'Enterprise';
          DOM.selectTicketUrgency.value = 'Critical';
        } else if (matchedRule.targetPriority === 'P2') {
          DOM.selectTicketImpact.value = 'Department';
          DOM.selectTicketUrgency.value = 'High';
        } else if (matchedRule.targetPriority === 'P3') {
          DOM.selectTicketImpact.value = 'Department';
          DOM.selectTicketUrgency.value = 'Medium';
        } else {
          DOM.selectTicketImpact.value = 'Single User';
          DOM.selectTicketUrgency.value = 'Low';
        }
        setupPriorityMatrixCalculator(DOM.selectTicketImpact, DOM.selectTicketUrgency, DOM.createPriorityPreviewBadge, DOM.createPriorityCalcLabel, DOM.selectTicketPriority);
      }
      showToast(`⚡ Business Rule: "${matchedRule.name}" applied (Routed to ${matchedRule.targetTeam})`, 'ai');
    }
  }

  // =========================================================================

  // =========================================================================
  // ITSM VIEWS: PROBLEM, CHANGE, KB, OMNICHANNEL, SETUP MODULES
  // =========================================================================

  // --- Problem Management ---
  function renderProblemManagement() {
    const container = document.getElementById('problem-cards-container');
    if (!container) return;

    let problems = state.problems;
    if (state.filterKedbOnly) {
      problems = problems.filter(p => p.isKedb);
    }
    const search = (document.getElementById('problem-filter-search')?.value || '').toLowerCase().trim();
    if (search) {
      problems = problems.filter(p => p.title.toLowerCase().includes(search) || p.rootCause.toLowerCase().includes(search) || p.ciName.toLowerCase().includes(search));
    }

    const statTotal = document.getElementById('stat-total-problems');
    if (statTotal) statTotal.textContent = `${state.problems.length} Problems`;
    const statKedb = document.getElementById('stat-kedb-count');
    if (statKedb) statKedb.textContent = `${state.problems.filter(p => p.isKedb).length} KEDB`;

    container.innerHTML = problems.map(p => `
      <div class="problem-card">
        <div class="problem-head">
          <span class="font-mono text-indigo font-bold">${p.id}</span>
          ${p.isKedb ? '<span class="badge-kedb">★ KEDB Known Error</span>' : '<span class="badge-tag">Investigating</span>'}
        </div>
        <h4 style="font-size:13.5px; font-weight:700; color:var(--text-zen-primary);">${escapeHtml(p.title)}</h4>
        <div style="font-size:12px; color:var(--text-zen-secondary);">
          <strong>Affected CI:</strong> <span class="ci-pill">${escapeHtml(p.ciName)}</span>
        </div>
        <div style="font-size:12px; color:var(--text-zen-muted); line-height:1.4;">
          <strong>Root Cause:</strong> ${escapeHtml(p.rootCause)}
        </div>
        ${p.workaround ? `
          <div class="kedb-workaround-box">
            <strong>KEDB Workaround:</strong>
            <p style="margin-top:2px;">${escapeHtml(p.workaround)}</p>
          </div>
        ` : ''}
        <div style="display:flex; align-items:center; justify-content:space-between; margin-top:4px;">
          <span class="text-xs text-muted">Linked: <strong>${p.linkedIncidents.length} Incidents</strong></span>
          <button class="btn btn-xs btn-zen-primary btn-open-whys" data-problem-id="${p.id}">
            <span>🔍 5-Whys Analyzer</span>
          </button>
        </div>
      </div>
    `).join('');

    container.querySelectorAll('.btn-open-whys').forEach(btn => {
      btn.addEventListener('click', () => {
        const pId = btn.getAttribute('data-problem-id');
        open5WhysModal(pId);
      });
    });
  }

  function open5WhysModal(problemId) {
    const p = state.problems.find(x => x.id === problemId);
    if (!p) return;

    const modal = document.getElementById('whys-modal-backdrop');
    const titleEl = document.getElementById('whys-modal-title');
    const bodyEl = document.getElementById('whys-modal-body');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `5-Whys Root Cause: ${p.id}`;

    bodyEl.innerHTML = `
      <div style="padding-bottom:8px; border-bottom:1px solid var(--border-zen-medium);">
        <h4 style="font-size:13px; font-weight:700;">${escapeHtml(p.title)}</h4>
        <span class="text-xs text-muted">CI: ${escapeHtml(p.ciName)} • Status: ${escapeHtml(p.status)}</span>
      </div>

      <div class="whys-chain-stepper">
        ${p.whys.map((w, idx) => `
          <div class="why-step-row">
            <div class="why-step-num">${idx + 1}</div>
            <div class="why-step-content">
              <strong>${escapeHtml(w.q)}</strong>
              <p>${escapeHtml(w.a)}</p>
            </div>
          </div>
        `).join('')}
      </div>

      <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:12px; margin-top:8px;">
        <strong class="text-indigo" style="font-size:12px;">★ Validated Root Cause Discovery</strong>
        <p style="font-size:12px; margin-top:2px; color:#1e3a8a;">${escapeHtml(p.rootCause)}</p>
      </div>

      <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:14px;">
        <button class="btn btn-sm btn-zen-outline" id="btn-close-whys-action">Close Analyzer</button>
        <button class="btn btn-sm btn-zen-primary" id="btn-publish-kedb-action">
          ${p.isKedb ? 'Update KEDB Record' : 'Publish to Known Error DB'}
        </button>
      </div>
    `;

    modal.classList.add('open');

    document.getElementById('btn-close-whys-action')?.addEventListener('click', () => {
      modal.classList.remove('open');
    });
    document.getElementById('btn-close-whys-modal')?.addEventListener('click', () => {
      modal.classList.remove('open');
    });
    document.getElementById('btn-publish-kedb-action')?.addEventListener('click', () => {
      p.isKedb = true;
      p.status = 'Known Error';
      modal.classList.remove('open');
      renderProblemManagement();
      showToast(`Problem ${p.id} verified and published to KEDB!`, 'success');
    });
  }

  // --- Change Management ---
  function renderChangeManagement() {
    const tbody = document.getElementById('changes-table-body');
    if (!tbody) return;

    let changes = state.changes;
    if (state.changeTypeFilter && state.changeTypeFilter !== 'ALL') {
      changes = changes.filter(c => c.type === state.changeTypeFilter);
    }
    const search = (document.getElementById('change-filter-search')?.value || '').toLowerCase().trim();
    if (search) {
      changes = changes.filter(c => c.title.toLowerCase().includes(search) || c.ciName.toLowerCase().includes(search) || c.lead.toLowerCase().includes(search));
    }

    tbody.innerHTML = changes.map(chg => {
      const riskClass = chg.riskScore < 30 ? 'risk-low' : chg.riskScore < 60 ? 'risk-med' : 'risk-high';
      const cabClass = chg.cabStatus.includes('Approved') ? 'badge-cab-approved' : 'badge-cab-pending';
      return `
        <tr>
          <td class="font-mono text-indigo font-bold">${chg.id}</td>
          <td><span class="badge-tag">${escapeHtml(chg.type)}</span></td>
          <td>
            <div style="font-weight:600; color:var(--text-zen-primary); font-size:12.5px;">${escapeHtml(chg.title)}</div>
            <div class="text-xs text-muted">${escapeHtml(chg.ciName)} • Lead: ${escapeHtml(chg.lead)}</div>
          </td>
          <td>
            <div class="risk-meter">
              <span class="risk-pill ${riskClass}">${chg.riskScore}% Risk</span>
              <span class="text-xs text-muted font-mono">(${chg.riskLevel})</span>
            </div>
          </td>
          <td><span class="${cabClass}">${escapeHtml(chg.cabStatus)}</span></td>
          <td class="font-mono text-xs">${escapeHtml(chg.scheduled)}</td>
          <td class="text-right">
            <div style="display:inline-flex; gap:6px;">
              ${chg.cabStatus.includes('Pending') ? `
                <button class="btn btn-xs btn-zen-primary btn-cab-approve" data-chg-id="${chg.id}">Approve</button>
                <button class="btn btn-xs btn-zen-subtle btn-cab-reject" data-chg-id="${chg.id}">Reject</button>
              ` : `
                <span class="text-emerald font-bold text-xs">✓ Ready</span>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.btn-cab-approve').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-chg-id');
        const c = state.changes.find(x => x.id === id);
        if (c) {
          c.cabStatus = 'Approved by CAB';
          renderChangeManagement();
          showToast(`Change ${id} approved by CAB voting quorum!`, 'success');
        }
      });
    });

    tbody.querySelectorAll('.btn-cab-reject').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-chg-id');
        const c = state.changes.find(x => x.id === id);
        if (c) {
          c.cabStatus = 'Revision Requested';
          renderChangeManagement();
          showToast(`Change ${id} sent back for risk assessment revision.`, 'info');
        }
      });
    });
  }

  // --- Knowledge Base ---
  function renderKnowledgeBase() {
    const container = document.getElementById('kb-articles-container');
    if (!container) return;

    let articles = state.kbArticles;
    if (state.kbCatFilter && state.kbCatFilter !== 'ALL') {
      articles = articles.filter(a => a.category === state.kbCatFilter);
    }
    const search = (document.getElementById('kb-filter-search')?.value || '').toLowerCase().trim();
    if (search) {
      articles = articles.filter(a => a.title.toLowerCase().includes(search) || a.summary.toLowerCase().includes(search));
    }

    container.innerHTML = articles.map(art => `
      <div class="kb-card" data-article-id="${art.id}">
        <div>
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
            <span class="badge-kcs">${escapeHtml(art.category)}</span>
            <span class="font-mono text-xs text-muted">${art.id}</span>
          </div>
          <h4 style="font-size:13.5px; font-weight:700; color:var(--text-zen-primary); line-height:1.4;">${escapeHtml(art.title)}</h4>
          <p class="text-xs text-muted mt-2" style="line-height:1.4;">${escapeHtml(art.summary)}</p>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; border-top:1px solid var(--border-zen-subtle); padding-top:10px; margin-top:8px;">
          <span class="text-xs text-secondary">By ${escapeHtml(art.author)}</span>
          <span class="text-xs text-indigo font-bold">Read Playbook →</span>
        </div>
      </div>
    `).join('');

    container.querySelectorAll('.kb-card').forEach(card => {
      card.addEventListener('click', () => {
        const aId = card.getAttribute('data-article-id');
        openKbArticleReader(aId);
      });
    });
  }

  function openKbArticleReader(articleId) {
    const art = state.kbArticles.find(x => x.id === articleId);
    if (!art) return;

    const modal = document.getElementById('kb-reader-backdrop');
    const titleEl = document.getElementById('kb-modal-title');
    const bodyEl = document.getElementById('kb-modal-body');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `${art.id}: ${art.title}`;

    bodyEl.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
        <span class="badge-kcs">${escapeHtml(art.category)}</span>
        <span class="badge-tag">Verified by SRE</span>
        <span class="text-xs text-muted">Author: ${escapeHtml(art.author)} • ${art.views} views</span>
      </div>

      <div style="font-size:12.5px; line-height:1.55; color:var(--text-zen-secondary);">
        ${art.content}
      </div>

      <div style="display:flex; align-items:center; justify-content:space-between; margin-top:20px; padding-top:14px; border-top:1px solid var(--border-zen-medium);">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="text-xs text-muted">Was this article helpful?</span>
          <button class="btn btn-xs btn-zen-outline" id="btn-kb-thumbs-up">👍 (${art.helpfulUp})</button>
          <button class="btn btn-xs btn-zen-outline" id="btn-kb-thumbs-down">👎 (${art.helpfulDown})</button>
        </div>
        <button class="btn btn-sm btn-zen-primary" id="btn-close-kb-action">Done Reading</button>
      </div>
    `;

    modal.classList.add('open');

    document.getElementById('btn-close-kb-action')?.addEventListener('click', () => modal.classList.remove('open'));
    document.getElementById('btn-close-kb-modal')?.addEventListener('click', () => modal.classList.remove('open'));

    document.getElementById('btn-kb-thumbs-up')?.addEventListener('click', () => {
      art.helpfulUp++;
      document.getElementById('btn-kb-thumbs-up').textContent = `👍 (${art.helpfulUp})`;
      showToast('Thank you for rating this runbook!', 'success');
    });
  }

  // --- Omnichannel Hub ---
  let ctiTimerInterval = null;

  function renderOmnichannelHub() {
    if (!ctiTimerInterval) {
      ctiTimerInterval = setInterval(() => {
        state.ctiSeconds++;
        const mins = String(Math.floor(state.ctiSeconds / 60)).padStart(2, '0');
        const secs = String(state.ctiSeconds % 60).padStart(2, '0');
        const timerEl = document.getElementById('cti-call-timer');
        if (timerEl) timerEl.textContent = `${mins}:${secs}`;
      }, 1000);
    }

    // Email-to-Ticket form submit
    const formEmail = document.getElementById('form-simulate-email');
    if (formEmail && !formEmail.hasAttribute('data-bound')) {
      formEmail.setAttribute('data-bound', 'true');
      formEmail.addEventListener('submit', (e) => {
        e.preventDefault();
        const from = document.getElementById('email-sim-from').value;
        const subj = document.getElementById('email-sim-subject').value;
        const body = document.getElementById('email-sim-body').value;

        const newId = `INC-${9040 + state.incidents.length + 1}`;
        const newInc = {
          id: newId,
          title: subj,
          description: `[Email Ingestion via support@opennow.io from ${from}]

${body}`,
          ci: 'CI-DB-001',
          ciName: 'PostgreSQL Primary (us-east-1)',
          category: 'Database & Storage',
          subcategory: 'PostgreSQL Aurora',
          item: 'Disk IOPS Throttling',
          impact: 'Enterprise',
          urgency: 'Critical',
          priority: 'P1',
          status: 'NEW',
          team: 'Database-Ops',
          caller: from,
          createdAt: 'Just now',
          slaSecondsRemaining: 3600,
          slaInitialSeconds: 3600,
          isPaused: false,
          totalPausedSeconds: 0,
          aiTriageDone: true,
          aiConfidence: '99.1%',
          worklogs: [],
          subtasks: [],
          timeline: [
            { time: 'Just now', user: 'Email Ingestion Gateway', text: `Ingested email from ${from}. Parsed subject & created P1 incident automatically.`, isAi: true }
          ]
        };

        state.incidents.unshift(newInc);
        renderTickets();

        const resBox = document.getElementById('email-parse-result');
        const resId = document.getElementById('email-parse-ticket-id');
        const resSummary = document.getElementById('email-parse-summary');
        if (resBox && resId && resSummary) {
          resBox.style.display = 'block';
          resId.textContent = newId;
          resSummary.innerHTML = `Subject: <strong>${escapeHtml(subj)}</strong><br>Parsed Priority: <span class="priority-pill pill-p1">P1</span> • Assigned to <strong>Database-Ops</strong>`;
        }

        showToast(`⚡ Email successfully converted to incident ${newId}!`, 'success');
      });
    }

    // Convert Call to Incident button
    const btnCallInc = document.getElementById('btn-convert-call-incident');
    if (btnCallInc && !btnCallInc.hasAttribute('data-bound')) {
      btnCallInc.setAttribute('data-bound', 'true');
      btnCallInc.addEventListener('click', () => {
        const notes = document.getElementById('cti-call-notes')?.value || 'Phone escalation from VP Sarah Lin.';
        const newId = `INC-${9040 + state.incidents.length + 1}`;
        const newInc = {
          id: newId,
          title: 'CTI Screen Pop Escalation: EKS Pod Evictions Degradation',
          description: `[Call logged from +1 (415) 555-0199 • Sarah Lin (VP Infrastructure)]

${notes}`,
          ci: 'CI-K8S-006',
          ciName: 'EKS Core Cluster (us-east-1)',
          category: 'Cloud & Infrastructure',
          subcategory: 'Kubernetes Cluster (EKS)',
          item: 'Pod CrashLoopBackOff Surge',
          impact: 'Enterprise',
          urgency: 'Critical',
          priority: 'P1',
          status: 'IN_PROGRESS',
          team: 'SRE-Core',
          caller: 'sarah.lin@opennow.io',
          createdAt: 'Just now',
          slaSecondsRemaining: 3600,
          slaInitialSeconds: 3600,
          isPaused: false,
          totalPausedSeconds: 0,
          aiTriageDone: true,
          aiConfidence: '99.8%',
          worklogs: [
            {
              id: 'WL-CTI',
              technician: 'Alex Rivera (SRE)',
              hours: 0,
              minutes: 15,
              rate: 150,
              cost: 37.50,
              isBillable: true,
              description: 'Took emergency phone bridge escalation from Sarah Lin.',
              loggedAt: 'Just now'
            }
          ],
          subtasks: [],
          timeline: [
            { time: 'Just now', user: 'CTI Softphone Screen Pop', text: 'Converted active call (+1-415-555-0199) to P1 incident.', isAi: true }
          ]
        };

        state.incidents.unshift(newInc);
        renderTickets();
        showToast(`📞 Active call converted into incident ${newId}!`, 'success');
        openTicketDrawer(newId);
      });
    }

    const btnCallWl = document.getElementById('btn-log-call-worklog');
    if (btnCallWl && !btnCallWl.hasAttribute('data-bound')) {
      btnCallWl.setAttribute('data-bound', 'true');
      btnCallWl.addEventListener('click', () => {
        showToast('Call recorded: 15m labor logged to Sarah Lin incident worklog.', 'info');
      });
    }

    const btnSimRing = document.getElementById('btn-simulate-new-call');
    if (btnSimRing && !btnSimRing.hasAttribute('data-bound')) {
      btnSimRing.setAttribute('data-bound', 'true');
      btnSimRing.addEventListener('click', () => {
        state.ctiSeconds = 0;
        showToast('📞 Incoming Call Screen Pop: Marcus Vance (Principal Security Engineer)...', 'ai');
      });
    }
  }

  // --- Setup Modules 7 & 8 (Email Channels & Phone CTI) ---
  function renderModuleEmailChannels() {
    return `
      <div class="rules-builder-card">
        <div style="display:flex; align-items:center; justify-content:space-between;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">Inbound Email Channels &amp; Mailbox Routing</h4>
            <p class="text-xs text-muted mt-1">Configure automated email ingestion addresses, IMAP polling intervals, and default categorization rules.</p>
          </div>
          <span class="badge-tag">2 Active Mailboxes</span>
        </div>

        <div style="background:var(--bg-zen-subtle); border:1px solid var(--border-zen-medium); border-radius:8px; padding:14px; margin-top:14px;">
          <span style="font-size:12px; font-weight:700; color:var(--text-zen-secondary); text-transform:uppercase;">Add Inbound Support Channel</span>
          <form id="form-add-email-chan" style="display:grid; grid-template-columns: 1.5fr 1.5fr 1fr 1fr auto; gap:8px; margin-top:8px; align-items:end;">
            <div>
              <label class="text-xs text-muted">Mailbox Address</label>
              <input type="email" id="in-email-addr" class="zen-form-control" placeholder="e.g. alerts@company.com" required style="height:32px;">
            </div>
            <div>
              <label class="text-xs text-muted">IMAP Host &amp; Port</label>
              <input type="text" id="in-email-host" class="zen-form-control" placeholder="imap.server.com:993" required style="height:32px;">
            </div>
            <div>
              <label class="text-xs text-muted">Default Team</label>
              <select id="in-email-team" class="zen-select w-full" style="height:32px;">
                <option value="SRE-Core">SRE-Core</option>
                <option value="Database-Ops">Database-Ops</option>
                <option value="Security-SecOps">SecOps</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-muted">Default Priority</label>
              <select id="in-email-prio" class="zen-select w-full" style="height:32px;">
                <option value="P1">P1</option>
                <option value="P2" selected>P2</option>
                <option value="P3">P3</option>
              </select>
            </div>
            <div>
              <button type="submit" class="btn btn-sm btn-zen-primary" style="height:32px;">+ Connect</button>
            </div>
          </form>
        </div>

        <div style="margin-top:14px; overflow-x:auto;">
          <table class="tech-table">
            <thead>
              <tr>
                <th>Channel Mailbox</th>
                <th>IMAP Protocol</th>
                <th>Routing Team</th>
                <th>Default SLA</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${state.emailChannels.map(c => `
                <tr>
                  <td><strong>${escapeHtml(c.email)}</strong></td>
                  <td class="font-mono text-xs">${escapeHtml(c.imap)} (SSL)</td>
                  <td><span class="badge-tag">${escapeHtml(c.team)}</span></td>
                  <td><span class="priority-pill pill-${c.priority.toLowerCase()}">${c.priority}</span></td>
                  <td><span class="badge-billable">● Active &amp; Polling (30s)</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  function bindModuleEmailChannelsEvents() {
    const form = document.getElementById('form-add-email-chan');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const em = document.getElementById('in-email-addr').value;
        const host = document.getElementById('in-email-host').value;
        const team = document.getElementById('in-email-team').value;
        const prio = document.getElementById('in-email-prio').value;
        state.emailChannels.push({ id: `EM-${Date.now()}`, email: em, imap: host, ssl: true, team, priority: prio, active: true });
        renderSetupCenter('email-channels');
        showToast(`Connected email channel ${em}!`, 'success');
      });
    }
  }

  function renderModulePhoneCti() {
    return `
      <div class="rules-builder-card">
        <div style="display:flex; align-items:center; justify-content:space-between;">
          <div>
            <h4 style="font-size:14px; font-weight:700;">Computer Telephony Integration (CTI) &amp; Softphone</h4>
            <p class="text-xs text-muted mt-1">Configure WebRTC softphone adapters, Amazon Connect / Twilio Flex screen pops, and audio AI transcription.</p>
          </div>
          <span class="badge-tag" style="background:#dcfce7; color:#166534; border-color:#86efac;">● WebRTC Engine Live</span>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:16px;">
          <div class="sla-policy-card">
            <h5 style="font-size:12.5px; font-weight:700;">CTI Gateway Settings</h5>
            
            <div class="form-group mt-2">
              <label class="text-xs text-muted">Primary CTI Provider</label>
              <select id="cti-provider-select" class="zen-select w-full" style="height:32px;">
                <option value="Amazon Connect" selected>Amazon Connect Contact Center</option>
                <option value="Twilio Flex">Twilio Flex CTI Integration</option>
                <option value="Genesys Cloud">Genesys Cloud CX Softphone</option>
                <option value="Built-in WebRTC">Built-in OpenNow WebRTC Softphone</option>
              </select>
            </div>

            <div class="form-group mt-2">
              <label class="text-xs text-muted">Softphone SIP / WebSocket Endpoint</label>
              <input type="text" class="zen-form-control font-mono" value="wss://connect.us-east-1.amazonaws.com/instance/opennow-sre/webrtc" style="height:32px;">
            </div>

            <button class="btn btn-sm btn-zen-primary mt-2" id="btn-save-cti-settings">Save CTI Integration</button>
          </div>

          <div class="sla-policy-card">
            <h5 style="font-size:12.5px; font-weight:700;">Screen Pop &amp; AI Whisper Behaviors</h5>

            <div style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">
              <label class="toggle-switch-label">
                <span>Trigger Screen Pop automatically on Incoming Ring</span>
                <input type="checkbox" class="zen-checkbox" checked>
              </label>
              <label class="toggle-switch-label">
                <span>Perform instant CMDB CI and User History matching</span>
                <input type="checkbox" class="zen-checkbox" checked>
              </label>
              <label class="toggle-switch-label">
                <span>Activate Real-time Whisper AI Voice Transcription</span>
                <input type="checkbox" class="zen-checkbox" checked>
              </label>
              <label class="toggle-switch-label">
                <span>Auto-draft Worklog entry upon call disconnect</span>
                <input type="checkbox" class="zen-checkbox" checked>
              </label>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function bindModulePhoneCtiEvents() {
    const btn = document.getElementById('btn-save-cti-settings');
    if (btn) {
      btn.addEventListener('click', () => {
        showToast('CTI Softphone configuration saved successfully!', 'success');
      });
    }
  }

  // ROUTING & VIEW SWITCHING
  // =========================================================================

  function switchView(viewName) {
    state.currentView = viewName;

    DOM.navItems.forEach(item => {
      if (item.getAttribute('data-view') === viewName) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    DOM.viewPanels.forEach(panel => {
      if (panel.id === `view-${viewName}`) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });

    if (DOM.breadcrumbView) {
      const titles = {
        'incident-command': 'Incident Command',
        'kanban-board': 'Unified Operations Kanban',
        'problem-management': 'Problem Management & KEDB',
        'change-management': 'Change Management & CAB',
        'omnichannel-hub': 'Omnichannel Hub (Email & CTI)',
        'service-catalog': 'Enterprise Service Catalog',
        'service-requests': 'Service Requests & Fulfillment Queue',
        'knowledge-base': 'Knowledge Base & KCS',
        'cmdb-topology': 'CMDB Topology Graph',
        'migration-studio': 'Top 10 Migration Hub',
        'ai-ops': 'AI Ops Center',
        'setup': 'Setup / Configurations'
      };
      DOM.breadcrumbView.textContent = titles[viewName] || viewName;
    }

    if (viewName === 'setup') {
      renderSetupCenter(state.activeSetupModule || 'dna');
    } else if (viewName === 'problem-management') {
      renderProblemManagement();
    } else if (viewName === 'change-management') {
      renderChangeManagement();
    } else if (viewName === 'knowledge-base') {
      renderKnowledgeBase();
    } else if (viewName === 'omnichannel-hub') {
      renderOmnichannelHub();
    } else if (viewName === 'service-requests') {
      renderServiceRequests();
    } else if (viewName === 'kanban-board') {
      renderUnifiedKanbanBoard();
    } else if (viewName === 'incident-command') {
      renderTickets();
    }
  }

  // =========================================================================
  // EVENT BINDINGS
  // =========================================================================

  function bindEvents() {
    DOM.navItems.forEach(item => {
      item.addEventListener('click', () => {
        const view = item.getAttribute('data-view');
        switchView(view);
      });
    });

    const headerIndustryPill = document.getElementById('header-industry-pill');
    if (headerIndustryPill) {
      headerIndustryPill.addEventListener('click', () => {
        switchView('setup');
        state.activeSetupModule = 'dna';
        renderSetupCenter('dna');
      });
    }

    if (DOM.brandHomeBtn) {
      DOM.brandHomeBtn.addEventListener('click', () => switchView('incident-command'));
    }

    if (DOM.btnToggleSidebar) {
      DOM.btnToggleSidebar.addEventListener('click', toggleSidebarCollapse);
    }
    if (DOM.btnMobileSidebarToggle) {
      DOM.btnMobileSidebarToggle.addEventListener('click', () => {
        DOM.sidebar.classList.toggle('mobile-open');
      });
    }

    if (DOM.btnZenModeToggle) {
      DOM.btnZenModeToggle.addEventListener('click', toggleZenMode);
    }
    if (DOM.btnSidebarZenToggle) {
      DOM.btnSidebarZenToggle.addEventListener('click', toggleZenMode);
    }
    if (DOM.btnZenExit) {
      DOM.btnZenExit.addEventListener('click', toggleZenMode);
    }

    if (DOM.viewModeKanban) {
      DOM.viewModeKanban.addEventListener('click', () => {
        DOM.viewModeKanban.classList.add('active');
        DOM.viewModeTable.classList.remove('active');
        DOM.kanbanContainer.style.display = 'grid';
        DOM.tableContainer.style.display = 'none';
        state.viewMode = 'kanban';
      });
    }

    if (DOM.viewModeTable) {
      DOM.viewModeTable.addEventListener('click', () => {
        DOM.viewModeTable.classList.add('active');
        DOM.viewModeKanban.classList.remove('active');
        DOM.kanbanContainer.style.display = 'none';
        DOM.tableContainer.style.display = 'block';
        state.viewMode = 'table';
      });
    }

    if (DOM.ticketFilterSearch) {
      DOM.ticketFilterSearch.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        if (DOM.ticketSearchClear) {
          DOM.ticketSearchClear.style.display = state.searchQuery ? 'block' : 'none';
        }
        renderTickets();
      });

      if (DOM.ticketSearchClear) {
        DOM.ticketSearchClear.addEventListener('click', () => {
          DOM.ticketFilterSearch.value = '';
          state.searchQuery = '';
          DOM.ticketSearchClear.style.display = 'none';
          renderTickets();
        });
      }
    }

    if (DOM.priorityFilterChips) {
      DOM.priorityFilterChips.forEach(chip => {
        chip.addEventListener('click', () => {
          DOM.priorityFilterChips.forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          state.priorityFilter = chip.getAttribute('data-filter-priority');
          renderTickets();
        });
      });
    }

    if (DOM.teamFilterSelect) {
      DOM.teamFilterSelect.addEventListener('change', (e) => {
        state.teamFilter = e.target.value;
        renderTickets();
      });
    }

    const kanbanSearch = document.getElementById('kanban-filter-search');
    if (kanbanSearch) {
      kanbanSearch.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderTickets();
      });
    }

    document.querySelectorAll('.kanban-p-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.kanban-p-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.priorityFilter = chip.getAttribute('data-filter-priority');
        renderTickets();
      });
    });

    document.querySelectorAll('.col-add-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openCreateModal();
      });
    });

    if (DOM.btnCreateIncidentTrigger) {
      DOM.btnCreateIncidentTrigger.addEventListener('click', () => openCreateModal());
    }
    if (DOM.btnCloseCreateModal) {
      DOM.btnCloseCreateModal.addEventListener('click', closeCreateModal);
    }
    if (DOM.btnCancelCreate) {
      DOM.btnCancelCreate.addEventListener('click', closeCreateModal);
    }


    // Unified Kanban Type Filter Chips
    document.querySelectorAll('.kanban-type-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.kanban-type-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.kanbanTypeFilter = chip.getAttribute('data-type');
        renderUnifiedKanbanBoard();
      });
    });

    const kanbanSearchInput = document.getElementById('kanban-filter-search');
    if (kanbanSearchInput) {
      kanbanSearchInput.addEventListener('input', () => {
        renderUnifiedKanbanBoard();
      });
    }

    // Service Requests Stage Filter Chips
    document.querySelectorAll('.req-stage-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.req-stage-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.requestsStageFilter = chip.getAttribute('data-stage');
        renderServiceRequests();
      });
    });

    const reqSearchInput = document.getElementById('requests-filter-search');
    if (reqSearchInput) {
      reqSearchInput.addEventListener('input', () => {
        renderServiceRequests();
      });
    }

    const btnJumpCatalog = document.getElementById('btn-jump-catalog-order');
    if (btnJumpCatalog) {
      btnJumpCatalog.addEventListener('click', () => {
        switchView('service-catalog');
      });
    }

    // Interactive 4-Step Wizard Navigation
    document.querySelectorAll('.btn-wizard-next').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const nextStep = parseInt(btn.getAttribute('data-next-step'), 10);
        
        // Validate Step 1
        if (state.wizardStep === 1) {
          const t = DOM.inputTicketTitle ? DOM.inputTicketTitle.value.trim() : '';
          const d = DOM.inputTicketDesc ? DOM.inputTicketDesc.value.trim() : '';
          if (!t) {
            showToast('Please enter an incident title before proceeding.', 'error');
            DOM.inputTicketTitle.focus();
            return;
          }
          if (!d) {
            showToast('Please provide telemetry symptoms or diagnostic details.', 'error');
            DOM.inputTicketDesc.focus();
            return;
          }
        }
        
        switchWizardStep(nextStep);
      });
    });

    document.querySelectorAll('.btn-wizard-prev').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const prevStep = parseInt(btn.getAttribute('data-prev-step'), 10);
        switchWizardStep(prevStep);
      });
    });

    document.querySelectorAll('.wizard-step-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const stepNum = parseInt(tab.getAttribute('data-wizard-step'), 10);
        // Only allow jumping back or to completed steps
        if (stepNum <= state.wizardStep || tab.classList.contains('completed')) {
          switchWizardStep(stepNum);
        }
      });
    });

    if (DOM.formCreateTicket) {
      DOM.formCreateTicket.addEventListener('submit', handleCreateTicketSubmit);
    }
    if (DOM.createModalBackdrop) {
      DOM.createModalBackdrop.addEventListener('click', (e) => {
        if (e.target === DOM.createModalBackdrop) closeCreateModal();
      });
    }

    if (DOM.selectTicketCategory) {
      DOM.selectTicketCategory.addEventListener('change', () => {
        applyBusinessRuleToCreateModal();
      });
    }
    if (DOM.selectTicketCi) {
      DOM.selectTicketCi.addEventListener('change', () => {
        applyBusinessRuleToCreateModal();
      });
    }

    // Resolution Modal Events
    if (DOM.btnCloseResolutionModal) DOM.btnCloseResolutionModal.addEventListener('click', closeResolutionModal);
    if (DOM.btnCancelResolution) DOM.btnCancelResolution.addEventListener('click', closeResolutionModal);
    if (DOM.formResolveTicket) DOM.formResolveTicket.addEventListener('submit', handleResolutionSubmit);
    if (DOM.resolutionModalBackdrop) {
      DOM.resolutionModalBackdrop.addEventListener('click', (e) => {
        if (e.target === DOM.resolutionModalBackdrop) closeResolutionModal();
      });
    }

    // Hold Reason Modal Events
    if (DOM.btnCloseHoldModal) DOM.btnCloseHoldModal.addEventListener('click', closeHoldModal);
    if (DOM.btnCancelHold) DOM.btnCancelHold.addEventListener('click', closeHoldModal);
    if (DOM.formHoldTicket) DOM.formHoldTicket.addEventListener('submit', handleHoldSubmit);
    if (DOM.holdModalBackdrop) {
      DOM.holdModalBackdrop.addEventListener('click', (e) => {
        if (e.target === DOM.holdModalBackdrop) closeHoldModal();
      });
    }

    if (DOM.inputTicketTitle) DOM.inputTicketTitle.addEventListener('input', handleLiveAiAssist);
    if (DOM.inputTicketDesc) DOM.inputTicketDesc.addEventListener('input', handleLiveAiAssist);

    if (DOM.drawerBackdrop) {
      DOM.drawerBackdrop.addEventListener('click', closeTicketDrawer);
    }

    // Top 10 Platform Sample Load Buttons
    document.querySelectorAll('.btn-sample-load').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const preset = btn.getAttribute('data-preset');
        handlePlatformSampleLoad(preset);
      });
    });

    document.querySelectorAll('.platform-card').forEach(card => {
      card.addEventListener('click', () => {
        const platform = card.getAttribute('data-platform');
        handlePlatformSampleLoad(platform);
      });
    });

    // Schema Tabs
    document.querySelectorAll('.schema-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.schema-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.activeSchemaTab = tab.getAttribute('data-schema-tab');
        renderRelationalSchemaVisualizer(state.currentPlatform, state.activeSchemaTab);
      });
    });

    if (DOM.btnBrowseFile && DOM.fileInput) {
      DOM.btnBrowseFile.addEventListener('click', () => DOM.fileInput.click());
      DOM.fileInput.addEventListener('change', () => handlePlatformSampleLoad('servicenow'));
    }
    if (DOM.dropzone) {
      DOM.dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        DOM.dropzone.classList.add('drag-active');
      });
      DOM.dropzone.addEventListener('dragleave', () => DOM.dropzone.classList.remove('drag-active'));
      DOM.dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        DOM.dropzone.classList.remove('drag-active');
        handlePlatformSampleLoad('servicenow');
      });
      DOM.dropzone.addEventListener('click', () => DOM.fileInput && DOM.fileInput.click());
    }

    if (DOM.btnExecuteMigration) {
      DOM.btnExecuteMigration.addEventListener('click', executeMigrationProcess);
    }
    if (DOM.btnCancelMigration) {
      DOM.btnCancelMigration.addEventListener('click', () => {
        if (DOM.migrationResultContainer) DOM.migrationResultContainer.style.display = 'none';
      });
    }
    if (DOM.btnViewIngestedTickets) {
      DOM.btnViewIngestedTickets.addEventListener('click', () => {
        switchView('incident-command');
      });
    }

    document.querySelectorAll('.btn-catalog-request').forEach(btn => {
      btn.addEventListener('click', () => {
        const template = btn.getAttribute('data-template');
        openCreateModal({
          priority: 'P2',
          impact: 'Department',
          urgency: 'High',
          ci: template === 'db-failover' ? 'CI-DB-001' : template === 'redis-scale' ? 'CI-CACHE-002' : template === 'laptop-prov' ? 'CI-AUTH-004' : template === 'cloud-iam' ? 'CI-AUTH-004' : 'CI-INGRESS-005',
          category: (template === 'laptop-prov' || template === 'cloud-iam' || template === 'sw-licenses' || template === 'vpn-access') ? 'Software & Applications' : 'Database & Storage',
          subcategory: template === 'laptop-prov' ? 'Order & Checkout Service' : template === 'cloud-iam' ? 'Auth & Identity (Auth0)' : 'PostgreSQL Aurora',
          item: template === 'laptop-prov' ? 'Hardware Provisioning' : template === 'cloud-iam' ? 'Privileged IAM Escalation' : 'Standard Service Request'
        });
        DOM.inputTicketTitle.value = `Standard Request: ${btn.closest('.catalog-card').querySelector('h3').textContent}`;
        DOM.inputTicketDesc.value = `Pre-approved operational deployment request generated from Enterprise Service Catalog. Ready for automated execution.`;
        handleLiveAiAssist();
      });
    });

    if (DOM.btnChaosSimulate) {
      DOM.btnChaosSimulate.addEventListener('click', triggerChaosSimulation);
    }

    if (DOM.cmdPaletteBtn) {
      DOM.cmdPaletteBtn.addEventListener('click', openCommandPalette);
    }
    if (DOM.cmdPaletteInput) {
      DOM.cmdPaletteInput.addEventListener('input', (e) => renderCommandResults(e.target.value));
    }
    if (DOM.cmdPaletteModal) {
      DOM.cmdPaletteModal.addEventListener('click', (e) => {
        if (e.target === DOM.cmdPaletteModal) closeCommandPalette();
      });
    }

    
    // Problem Management Events
    document.getElementById('btn-toggle-kedb')?.addEventListener('click', () => {
      state.filterKedbOnly = !state.filterKedbOnly;
      const btn = document.getElementById('btn-toggle-kedb');
      if (btn) btn.classList.toggle('active', state.filterKedbOnly);
      renderProblemManagement();
    });

    document.getElementById('btn-filter-problems-all')?.addEventListener('click', () => {
      state.filterKedbOnly = false;
      document.getElementById('btn-toggle-kedb')?.classList.remove('active');
      renderProblemManagement();
    });

    document.getElementById('problem-filter-search')?.addEventListener('input', renderProblemManagement);

    // Change Management Events
    document.querySelectorAll('.change-type-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.change-type-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.changeTypeFilter = chip.getAttribute('data-type');
        renderChangeManagement();
      });
    });

    document.getElementById('change-filter-search')?.addEventListener('input', renderChangeManagement);

    // Knowledge Base Events
    document.querySelectorAll('.kb-cat-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.kb-cat-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.kbCatFilter = chip.getAttribute('data-kb-cat');
        renderKnowledgeBase();
      });
    });

    document.getElementById('kb-filter-search')?.addEventListener('input', renderKnowledgeBase);

    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openCommandPalette();
      } else if (e.key === 'Escape') {
        closeCommandPalette();
        closeCreateModal();
        closeResolutionModal();
        closeHoldModal();
        closeTicketDrawer();
        if (DOM.cmdbInspectorPanel) DOM.cmdbInspectorPanel.classList.remove('open');
      } else if ((e.key === 'z' || e.key === 'Z') && !e.target.matches('input, textarea, select')) {
        toggleZenMode();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        toggleSidebarCollapse();
      }
    });
  }

  // =========================================================================
  // TOAST NOTIFICATION SYSTEM
  // =========================================================================

  function showToast(message, type = 'info') {
    if (!DOM.toastsContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : type === 'error' ? '⚠' : type === 'ai' ? '✦' : 'ℹ';
    toast.innerHTML = `<strong>${icon}</strong> <span>${escapeHtml(message)}</span>`;

    DOM.toastsContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 300ms ease, transform 300ms ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // =========================================================================
  // UTILITIES
  // =========================================================================

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function escapeXml(str) {
    return escapeHtml(str);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }

})();
