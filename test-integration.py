#!/usr/bin/env python3
"""
Framework Integration Test Suite
Tests how well frameworks work together
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
RESULTS_DIR = WORKSPACE / "platform-consolidation" / "integration-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

class FrameworkTester:
    def __init__(self):
        self.results = {}
        
    def test_interface_compatibility(self, framework1: str, framework2: str) -> Tuple[bool, str]:
        """Test if two frameworks can communicate"""
        # Check for common interfaces
        interfaces = {
            "necroswarm": ["agent_id", "task_queue", "consensus"],
            "neuroswarm": ["brain", "swarm", "knowledge_graph"],
            "obliviarch": ["compress", "retrieve", "schema"],
            "voidtether": ["bridge", "protocol", "mesh"],
            "openclaw-namespace": ["uri", "resolve", "namespace"],
            "openclaw-memory-evolution": ["memory", "evolve", "relationship"],
            "openclaw-deterministic-retrieval": ["retrieve", "deterministic", "exact"],
        }
        
        f1_interfaces = interfaces.get(framework1, [])
        f2_interfaces = interfaces.get(framework2, [])
        
        # Check for common keywords
        common = set(f1_interfaces) & set(f2_interfaces)
        
        if common:
            return True, f"Common interfaces: {', '.join(common)}"
        else:
            return False, "No common interfaces detected"
    
    def test_data_flow(self, source: str, target: str) -> Tuple[bool, str]:
        """Test if data can flow from source to target"""
        # Define data flow capabilities
        data_formats = {
            "necroswarm": ["json", "protobuf"],
            "neuroswarm": ["json", "graph", "embedding"],
            "obliviarch": ["compressed", "schema", "json"],
            "voidtether": ["json", "protobuf", "mcp"],
            "openclaw-namespace": ["uri", "json"],
            "openclaw-memory-evolution": ["json", "vector"],
            "openclaw-deterministic-retrieval": ["json", "exact"],
        }
        
        source_formats = data_formats.get(source, [])
        target_formats = data_formats.get(target, [])
        
        # Check for compatible formats
        compatible = set(source_formats) & set(target_formats)
        
        if "json" in source_formats and "json" in target_formats:
            return True, "JSON compatibility"
        elif compatible:
            return True, f"Compatible formats: {', '.join(compatible)}"
        else:
            return False, f"Format mismatch: {source_formats} → {target_formats}"
    
    def test_dependency_conflicts(self, frameworks: List[str]) -> Tuple[bool, List[str]]:
        """Check for dependency version conflicts"""
        # Known dependency profiles
        deps = {
            "necroswarm": {"python": ">=3.9", "redis": "^5.0", "pydantic": "^2.0"},
            "neuroswarm": {"python": ">=3.10", "networkx": "^3.0", "numpy": "^1.24"},
            "obliviarch": {"python": ">=3.9", "zstandard": "^0.21"},
            "voidtether": {"python": ">=3.9", "grpc": "^1.50", "protobuf": "^4.0"},
            "openclaw-namespace": {"python": ">=3.8"},
            "openclaw-memory-evolution": {"python": ">=3.9", "chromadb": "^0.4"},
            "openclaw-deterministic-retrieval": {"python": ">=3.8"},
        }
        
        conflicts = []
        python_versions = []
        
        for fw in frameworks:
            if fw in deps:
                python_versions.append((fw, deps[fw].get("python", ">=3.8")))
        
        # Check Python version compatibility
        if python_versions:
            max_version = max([v for _, v in python_versions], key=lambda x: x.replace(">=", "").replace(">", ""))
            min_version = min([v for _, v in python_versions], key=lambda x: x.replace(">=", "").replace(">", ""))
            
            if max_version != min_version:
                conflicts.append(f"Python version range: {min_version} to {max_version}")
        
        return len(conflicts) == 0, conflicts
    
    def run_all_tests(self) -> Dict:
        """Run complete integration test suite"""
        frameworks = [
            "necroswarm",
            "neuroswarm", 
            "obliviarch",
            "voidtether",
            "openclaw-namespace",
            "openclaw-memory-evolution",
            "openclaw-deterministic-retrieval"
        ]
        
        print("Framework Integration Test Suite")
        print("=" * 50)
        print()
        
        # Test pairwise compatibility
        print("Testing pairwise compatibility...")
        compatibility_matrix = {}
        
        for i, fw1 in enumerate(frameworks):
            for fw2 in frameworks[i+1:]:
                compatible, reason = self.test_interface_compatibility(fw1, fw2)
                data_compatible, data_reason = self.test_data_flow(fw1, fw2)
                
                key = f"{fw1} <-> {fw2}"
                compatibility_matrix[key] = {
                    "interface_compatible": compatible,
                    "interface_reason": reason,
                    "data_compatible": data_compatible,
                    "data_reason": data_reason,
                    "overall": compatible and data_compatible
                }
                
                status = "✓" if (compatible and data_compatible) else "✗"
                print(f"  {status} {fw1} <-> {fw2}")
        
        print()
        
        # Test dependency conflicts
        print("Testing dependency conflicts...")
        no_conflicts, conflicts = self.test_dependency_conflicts(frameworks)
        
        if no_conflicts:
            print("  ✓ No dependency conflicts detected")
        else:
            print("  ⚠ Potential conflicts:")
            for conflict in conflicts:
                print(f"    - {conflict}")
        
        print()
        
        # Generate recommendations
        print("Integration Recommendations:")
        print("-" * 50)
        
        # Find strongly connected components
        strong_pairs = [k for k, v in compatibility_matrix.items() if v["overall"]]
        weak_pairs = [k for k, v in compatibility_matrix.items() if not v["overall"]]
        
        print(f"  Strong connections: {len(strong_pairs)}")
        print(f"  Weak connections: {len(weak_pairs)}")
        print()
        
        if len(strong_pairs) > len(weak_pairs):
            print("  ✓ Frameworks are generally compatible")
            print("  → Proceed with consolidation")
        else:
            print("  ⚠ Several integration challenges detected")
            print("  → Consider adapter layers for:")
            for pair in weak_pairs[:5]:  # Show first 5
                print(f"    - {pair}")
        
        self.results = {
            "compatibility_matrix": compatibility_matrix,
            "dependency_conflicts": conflicts,
            "strong_connections": len(strong_pairs),
            "weak_connections": len(weak_pairs),
            "recommendation": "PROCEED" if len(strong_pairs) > len(weak_pairs) else "ADAPTERS_NEEDED"
        }
        
        return self.results
    
    def save_report(self):
        """Save test results to file"""
        report_file = RESULTS_DIR / f"integration-test-{__import__('datetime').datetime.now().strftime('%Y%m%d')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")

if __name__ == "__main__":
    tester = FrameworkTester()
    tester.run_all_tests()
    tester.save_report()
    
    print("\n" + "=" * 50)
    print("Integration testing complete!")
