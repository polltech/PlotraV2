import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../models/farm.dart';
import '../widgets/farm_card.dart';
import '../widgets/stat_card.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> 
    with SingleTickerProviderStateMixin {
  
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  List<Farm> _farms = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    );
    
    _loadData();
  }

  Future<void> _loadData() async {
    // Simulate loading farms - replace with actual API call
    await Future.delayed(const Duration(milliseconds: 800));
    
    // Mock farms for now
    setState(() {
      _farms = [
        Farm(
          id: '1',
          name: 'Kipawa Farm',
          polygon: [],
          area: 2.5,
          status: 'certified',
          createdAt: DateTime.now(),
        ),
        Farm(
          id: '2',
          name: 'Karen Estate',
          polygon: [],
          area: 5.2,
          status: 'submitted',
          createdAt: DateTime.now(),
        ),
        Farm(
          id: '3',
          name: 'Ruiru Plot',
          polygon: [],
          area: 1.8,
          status: 'draft',
          createdAt: DateTime.now(),
        ),
      ];
      _isLoading = false;
    });
    
    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);
    final userName = auth.user?.name ?? 'Farmer';

    return Scaffold(
      backgroundColor: const Color(0xFF0a0a0a),
      body: CustomScrollView(
        slivers: [
          // Custom App Bar
          SliverAppBar(
            expandedHeight: 140,
            floating: false,
            pinned: true,
            backgroundColor: const Color(0xFF0a0a0a),
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [Color(0xFF0a0a0a), Color(0xFF1a1a1a)],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
                ),
                child: SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 50, 20, 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 45,
                              height: 45,
                              decoration: BoxDecoration(
                                gradient: const LinearGradient(
                                  colors: [Color(0xFFd4a853), Color(0xFFe8c97a)],
                                ),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.agriculture,
                                color: Colors.black,
                                size: 24,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Plotra',
                                  style: TextStyle(
                                    fontSize: 22,
                                    fontWeight: FontWeight.w800,
                                    color: Colors.white,
                                    letterSpacing: -0.5,
                                  ),
                                ),
                                Text(
                                  'Welcome, $userName',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFF8a8a8a),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        Row(
                          children: [
                            _buildIconButton(
                              icon: Icons.notifications_outlined,
                              onTap: () {},
                              badge: 3,
                            ),
                            const SizedBox(width: 8),
                            _buildIconButton(
                              icon: Icons.refresh,
                              onTap: _loadData,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Content
          SliverToBoxAdapter(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: _isLoading
                  ? _buildLoadingState()
                  : Column(
                      children: [
                        const SizedBox(height: 20),
                        
                        // Stats Row
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          child: Row(
                            children: [
                              Expanded(
                                child: StatCard(
                                  title: 'Total Farms',
                                  value: _farms.length.toString(),
                                  icon: Icons.agriculture,
                                  color: const Color(0xFFd4a853),
                                  gradient: const LinearGradient(
                                    colors: [Color(0xFF2d5016), Color(0xFF4a7c24)],
                                  ),
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: StatCard(
                                  title: 'Verified',
                                  value: _farms
                                      .where((f) => f.isVerified)
                                      .length
                                      .toString(),
                                  icon: Icons.check_circle,
                                  color: Colors.green,
                                  gradient: const LinearGradient(
                                    colors: [Color(0xFF166534), Color(0xFF22c55e)],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 30),
                        
                        // Section Header
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                'My Farms',
                                style: TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              TextButton(
                                onPressed: () {},
                                child: const Text(
                                  'See All',
                                  style: TextStyle(
                                    color: Color(0xFFd4a853),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        
                        const SizedBox(height: 16),
                        
                        // Farms List
                        ListView.separated(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          itemCount: _farms.length,
                          separatorBuilder: (context, index) => 
                              const SizedBox(height: 12),
                          itemBuilder: (context, index) {
                            final farm = _farms[index];
                            return FarmCard(
                              farm: farm,
                              onTap: () {
                                Navigator.pushNamed(
                                  context,
                                  '/map',
                                  arguments: farm,
                                );
                              },
                              onEdit: () {
                                Navigator.pushNamed(
                                  context,
                                  '/map',
                                  arguments: farm,
                                );
                              },
                            );
                          },
                        ),

                        const SizedBox(height: 100),
                      ],
                    ),
              ),
            ),
          ),
        ],
      ),
      
      // Floating Action Button
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.pushNamed(context, '/map');
        },
        backgroundColor: const Color(0xFFd4a853),
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add, size: 28),
        label: const Text(
          'Add Farm',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 16,
          ),
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        elevation: 8,
        shadowColor: const Color(0xFFd4a853).withOpacity(0.5),
      ),
    );
  }

  Widget _buildIconButton({
    required IconData icon,
    required VoidCallback onTap,
    int? badge,
  }) {
    return Stack(
      children: [
        GestureDetector(
          onTap: onTap,
          child: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFF1a1a1a),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF333333)),
            ),
            child: Icon(
              icon,
              color: Colors.white,
              size: 20,
            ),
          ),
        ),
        if (badge != null && badge > 0)
          Positioned(
            right: -5,
            top: -5,
            child: Container(
              padding: const EdgeInsets.all(4),
              decoration: const BoxDecoration(
                color: Colors.red,
                shape: BoxShape.circle,
              ),
              constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
              child: Text(
                badge.toString(),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.only(top: 100),
        child: Column(
          children: [
            Shimmer.fromColors(
              baseColor: const Color(0xFFd4a853).withOpacity(0.3),
              highlightColor: const Color(0xFFd4a853),
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: const Color(0xFF1a1a1a),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(Icons.agriculture, size: 40),
              ),
            ),
            const SizedBox(height: 30),
            const Text(
              'Loading your farms...',
              style: TextStyle(
                color: Color(0xFF8a8a8a),
                fontSize: 16,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
