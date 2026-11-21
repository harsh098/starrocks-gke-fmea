import com.sleepycat.je.rep.util.ReplicationGroupAdmin;
import java.net.InetSocketAddress;
import java.util.HashSet;

/** Read the live group over JE's admin protocol. Does not open local metadata. */
public class ReadJeGroup {
    public static void main(String[] args) {
        var helpers = new HashSet<InetSocketAddress>();
        for (String host : args) {
            helpers.add(new InetSocketAddress(host, 9010));
        }
        var group = new ReplicationGroupAdmin("PALO_JOURNAL_GROUP", helpers)
                .getGroup().getRepGroupImpl();
        System.out.println("group=" + group.getName() + " uuid=" + group.getUUID()
                + " nodeIdSequence=" + group.getNodeIdSequence()
                + " changeVersion=" + group.getChangeVersion());
        for (var node : group.getElectableMembers()) {
            System.out.println("id=" + node.getNodeId() + " name=" + node.getName()
                    + " host=" + node.getHostPortPair() + " removed=" + node.isRemoved());
        }
    }
}
